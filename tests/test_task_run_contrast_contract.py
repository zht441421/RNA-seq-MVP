import csv
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


FORBIDDEN_PUBLIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "token",
    "password",
    "secret",
)


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def _assert_safe(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_PUBLIC_FRAGMENTS)


def _write_inputs(input_root: Path) -> tuple[str, str]:
    demo_dir = input_root / "demo"
    demo_dir.mkdir(parents=True)
    (demo_dir / "metadata.csv").write_text(
        "\n".join(
            [
                "sample_id,condition",
                "sample_1,control",
                "sample_2,control",
                "sample_3,treatment",
                "sample_4,treatment",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (demo_dir / "counts.csv").write_text(
        "\n".join(
            [
                "gene_id,sample_1,sample_2,sample_3,sample_4",
                "GeneA,10,10,30,30",
                "GeneB,90,90,70,70",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return "demo/metadata.csv", "demo/counts.csv"


def _create_ready_task(client: TestClient, metadata_file: str, count_matrix_file: str) -> str:
    task_id = client.post("/task/create", json={}).json()["task_id"]
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post(
        "/task/qc",
        json=_qc_payload(task_id, metadata_file, count_matrix_file),
    ).status_code == 200
    return task_id


def _plan_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _qc_payload(task_id: str, metadata_file: str, count_matrix_file: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "metadata_file": metadata_file,
        "count_matrix_file": count_matrix_file,
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _run_payload(task_id: str, metadata_file: str, count_matrix_file: str) -> dict[str, object]:
    return {
        **_plan_payload(task_id),
        "metadata_file": metadata_file,
        "count_matrix_file": count_matrix_file,
        "execution_mode": "minimal_real",
    }


def test_task_run_accepts_contrast_fields_and_writes_minimal_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    client = TestClient(app)
    task_id = _create_ready_task(client, metadata_file, count_matrix_file)

    response = client.post(
        "/task/run",
        json={
            **_run_payload(task_id, metadata_file, count_matrix_file),
            "contrast_column": "condition",
            "contrast_numerator": "treatment",
            "contrast_denominator": "control",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "minimal_analysis_completed"
    _assert_safe(body)

    output_dir = output_root / "tasks" / task_id
    execution_summary = json.loads(
        (output_dir / "execution_summary.json").read_text(encoding="utf-8")
    )
    run_manifest = json.loads(
        (output_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    report_text = (output_dir / "report.md").read_text(encoding="utf-8")
    with (output_dir / "differential_expression_results.csv").open(
        "r",
        encoding="utf-8",
        newline="",
    ) as input_file:
        rows = list(csv.DictReader(input_file))

    assert execution_summary["contrast"]["direction"] == "treatment_vs_control"
    assert run_manifest["contrast"]["contrast_numerator"] == "treatment"
    assert rows[0]["contrast_direction"] == "treatment_vs_control"
    assert "Higher in treatment relative to control" in report_text
    assert float(rows[0]["log2_fold_change"]) > 0
    _assert_safe(execution_summary)
    _assert_safe(run_manifest)


def test_task_run_invalid_contrast_returns_deterministic_validation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    client = TestClient(app)
    task_id = _create_ready_task(client, metadata_file, count_matrix_file)

    response = client.post(
        "/task/run",
        json={
            **_run_payload(task_id, metadata_file, count_matrix_file),
            "contrast_column": "condition",
            "contrast_numerator": "case",
            "contrast_denominator": "control",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["error_code"] == "CONTRAST_VALIDATION_FAILED"
    assert any("contrast_numerator" in error for error in body["detail"]["errors"])
    assert not (output_root / "tasks" / task_id / "execution_summary.json").exists()
    _assert_safe(body)


def test_task_run_without_explicit_contrast_preserves_inferred_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    client = TestClient(app)
    task_id = _create_ready_task(client, metadata_file, count_matrix_file)

    response = client.post(
        "/task/run",
        json=_run_payload(task_id, metadata_file, count_matrix_file),
    )

    assert response.status_code == 200
    output_dir = output_root / "tasks" / task_id
    execution_summary = json.loads(
        (output_dir / "execution_summary.json").read_text(encoding="utf-8")
    )
    with (output_dir / "differential_expression_results.csv").open(
        "r",
        encoding="utf-8",
        newline="",
    ) as input_file:
        rows = list(csv.DictReader(input_file))

    assert execution_summary["contrast"]["contrast_source"] == "inferred"
    assert execution_summary["contrast"]["direction"] == "treatment_vs_control"
    assert rows[0]["contrast_direction"] == "treatment_vs_control"
    assert float(rows[0]["log2_fold_change"]) > 0
