import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import get_task, reset_registry


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
ANALYSIS_OUTPUT_FILES = (
    "run_manifest.json",
    "execution_summary.json",
    "qc_summary.json",
    "normalized_counts_cpm.csv",
    "differential_expression_results.csv",
    "report.md",
)


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


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
                "GeneA,100,120,250,260",
                "GeneB,5,3,4,6",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return "demo/metadata.csv", "demo/counts.csv"


def _create_task(client: TestClient) -> str:
    response = client.post("/task/create", json={})
    assert response.status_code == 200
    return response.json()["task_id"]


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


def _run_payload(
    task_id: str,
    metadata_file: str,
    count_matrix_file: str,
    *,
    method_field: str,
) -> dict[str, object]:
    return {
        **_plan_payload(task_id),
        "metadata_file": metadata_file,
        "count_matrix_file": count_matrix_file,
        "execution_mode": "minimal_real",
        method_field: "deseq2",
    }


def _assert_no_forbidden_public_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_PUBLIC_FRAGMENTS)


@pytest.mark.parametrize("method_field", ["analysis_method", "formal_de_method"])
def test_task_run_rejects_formal_method_without_generating_outputs(
    method_field: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / f"inputs_{method_field}"
    output_root = tmp_path / f"outputs_{method_field}"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    client = TestClient(app)
    task_id = _create_task(client)
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post(
        "/task/qc",
        json=_qc_payload(task_id, metadata_file, count_matrix_file),
    ).status_code == 200

    response = client.post(
        "/task/run",
        json=_run_payload(
            task_id,
            metadata_file,
            count_matrix_file,
            method_field=method_field,
        ),
    )

    assert response.status_code == 501
    body = response.json()
    assert body["detail"]["error_code"] == "FORMAL_DE_METHOD_NOT_IMPLEMENTED"
    assert body["detail"]["requested_method"] == "deseq2"
    assert body["detail"]["supported_current_methods"] == ["minimal_cpm_log2fc"]
    assert body["detail"]["supported_future_formal_methods"] == [
        "deseq2",
        "edger",
        "limma",
    ]
    _assert_no_forbidden_public_fragments(body)

    output_dir = output_root / "tasks" / task_id
    for filename in ANALYSIS_OUTPUT_FILES:
        assert not (output_dir / filename).exists()

    status_response = client.get(f"/task/{task_id}/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "qc_placeholder_ready"

    task = get_task(task_id)
    assert task is not None
    event_types = [event.event_type for event in task.lifecycle_events]
    assert "minimal_rnaseq_executed" not in event_types
    task_payload = task.model_dump() if hasattr(task, "model_dump") else task.dict()
    assert "minimal_analysis_completed" not in json.dumps(task_payload)
