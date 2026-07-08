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
FORBIDDEN_RESULT_CLAIMS = (
    "pvalue",
    "padj",
    "qvalue",
    "enrichment",
    "pathway",
)


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def _write_inputs(input_root: Path) -> tuple[str, str]:
    demo_dir = input_root / "demo"
    demo_dir.mkdir(parents=True)
    metadata_file = demo_dir / "metadata.csv"
    count_matrix_file = demo_dir / "counts.csv"
    metadata_file.write_text(
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
    count_matrix_file.write_text(
        "\n".join(
            [
                "gene_id,sample_1,sample_2,sample_3,sample_4",
                "GeneA,100,120,250,260",
                "GeneB,5,3,4,6",
                "GeneC,1,1,0,0",
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


def _run_payload(task_id: str, metadata_file: str, count_matrix_file: str) -> dict[str, object]:
    return {
        **_plan_payload(task_id),
        "metadata_file": metadata_file,
        "count_matrix_file": count_matrix_file,
        "execution_mode": "minimal_real",
    }


def _assert_no_forbidden_public_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_PUBLIC_FRAGMENTS)


def _assert_no_forbidden_result_claims(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    assert all(fragment not in text for fragment in FORBIDDEN_RESULT_CLAIMS)


def test_task_run_minimal_rnaseq_writes_real_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
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
        json=_run_payload(task_id, metadata_file, count_matrix_file),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert body["status"] == "minimal_analysis_completed"
    assert [artifact["path"] for artifact in body["artifacts"]] == [
        f"tasks/{task_id}/run_manifest.json",
        f"tasks/{task_id}/execution_summary.json",
        f"tasks/{task_id}/qc_summary.json",
        f"tasks/{task_id}/normalized_counts_cpm.csv",
        f"tasks/{task_id}/differential_expression_results.csv",
        f"tasks/{task_id}/report.md",
    ]
    assert all(artifact["available"] is True for artifact in body["artifacts"])
    _assert_no_forbidden_public_fragments(body)

    output_dir = output_root / "tasks" / task_id
    expected_files = {
        "run_manifest.json",
        "execution_summary.json",
        "qc_summary.json",
        "normalized_counts_cpm.csv",
        "differential_expression_results.csv",
        "report.md",
    }
    assert output_dir.is_dir()
    assert expected_files == {path.name for path in output_dir.iterdir()}
    for filename in expected_files:
        assert (output_dir / filename).is_file()
        _assert_no_forbidden_result_claims(output_dir / filename)

    qc_summary = json.loads((output_dir / "qc_summary.json").read_text(encoding="utf-8"))
    execution_summary = json.loads(
        (output_dir / "execution_summary.json").read_text(encoding="utf-8")
    )
    with (output_dir / "differential_expression_results.csv").open(
        "r",
        encoding="utf-8",
        newline="",
    ) as result_file:
        result_fieldnames = csv.DictReader(result_file).fieldnames or []

    assert qc_summary["sample_count"] == 4
    assert qc_summary["gene_count"] == 3
    assert qc_summary["retained_gene_count_after_filtering"] == 2
    assert execution_summary["real_execution_performed"] is True
    assert execution_summary["external_tools_called"] is False
    assert execution_summary["statistical_test_performed"] is False
    assert {"pvalue", "padj", "qvalue"}.isdisjoint(result_fieldnames)
