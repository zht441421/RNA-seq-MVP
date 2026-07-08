from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


FORBIDDEN_REPORT_FRAGMENTS = (
    "pvalue",
    "padj",
    "qvalue",
    "significant deg",
    "significant differentially expressed gene",
    "enrichment",
    "pathway",
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


def test_minimal_rnaseq_report_contains_required_sections_and_boundaries(
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
    report_path = output_root / "tasks" / task_id / "report.md"
    assert report_path.is_file()
    report = report_path.read_text(encoding="utf-8")

    for heading in (
        "# Minimal Bulk RNA-seq MVP Report",
        "## Analysis summary",
        "## Input validation summary",
        "## QC summary",
        "## Normalization summary",
        "## Preliminary log2 fold-change ranking",
        "## Top preliminary ranked genes",
        "## Generated artifacts",
        "## Limitations",
        "## Recommended next steps",
    ):
        assert heading in report

    assert "CPM normalization was computed." in report
    assert "CPM is library-size normalization" in report
    assert "group-level mean CPM comparison" in report
    assert "No DESeq2, edgeR, or limma was run." in report
    assert "No p-values or adjusted p-values are reported." in report
    assert "No formal statistical test" in report
    assert "No statistical test was performed." in report
    assert "| gene_id | mean_cpm_group_1 | mean_cpm_group_2 | log2_fold_change | total_count |" in report
    assert "| GeneB |" in report

    for artifact_name in (
        "run_manifest.json",
        "execution_summary.json",
        "qc_summary.json",
        "normalized_counts_cpm.csv",
        "differential_expression_results.csv",
        "report.md",
    ):
        assert artifact_name in report

    lowered_report = report.lower()
    for forbidden_fragment in FORBIDDEN_REPORT_FRAGMENTS:
        assert forbidden_fragment not in lowered_report
