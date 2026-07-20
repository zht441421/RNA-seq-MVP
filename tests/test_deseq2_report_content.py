from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import deseq2_execution
from backend.app.services.formal_de_preflight import CommandResult
from backend.app.services.task_registry import reset_registry


FORBIDDEN_REPORT_FRAGMENTS = (
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
                "GeneB,20,22,10,12",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return "demo/metadata.csv", "demo/counts.csv"


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
        "execution_mode": "formal_de_real",
        "formal_de_method": "deseq2",
    }


def _ready_preflight() -> dict:
    return {
        "ready": True,
        "r_available": True,
        "rscript_available": True,
        "biocmanager_available": True,
        "deseq2_available": True,
        "warnings": [],
        "limitations": [],
    }


def _write_mock_results(output_path: str) -> None:
    Path(output_path).write_text(
        "\n".join(
            [
                "gene_id,baseMean,log2FoldChange,lfcSE,stat,pvalue,padj",
                "GeneA,182.5,1.1,0.2,5.5,0.001,0.002",
                "GeneB,16.0,-0.9,0.3,-3.0,0.02,0.04",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_deseq2_report_contains_formal_method_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    metadata_file, count_matrix_file = _write_inputs(input_root)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    monkeypatch.setattr(
        deseq2_execution.formal_de_preflight,
        "run_deseq2_preflight",
        _ready_preflight,
    )

    def fake_run(args: list[str], timeout_seconds: int = 120, working_directory=None) -> CommandResult:
        _write_mock_results(args[-1])
        return CommandResult(args=args, returncode=0)

    monkeypatch.setattr(deseq2_execution, "run_command_safely", fake_run)

    client = TestClient(app)
    task_id = client.post("/task/create", json={}).json()["task_id"]
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post(
        "/task/qc",
        json=_qc_payload(task_id, metadata_file, count_matrix_file),
    ).status_code == 200
    assert client.post(
        "/task/run",
        json=_run_payload(task_id, metadata_file, count_matrix_file),
    ).status_code == 200

    report_path = output_root / "tasks" / task_id / "report.md"
    report = report_path.read_text(encoding="utf-8")

    assert "DESeq2" in report
    assert "Design formula: `~ condition`" in report
    assert "Statistical test performed: true" in report
    assert "P-values available: true" in report
    assert "Adjusted p-values available: true" in report
    assert "Result artifact: `deseq2_results.csv`" in report
    assert "DESeq2 interpretation summary" in report
    assert "padj <= 0.05" in report
    assert "abs(log2FoldChange) >= 1.0" in report
    assert "Statistical significance is not the same as biological significance" in report
    assert "log2FoldChange direction depends on DESeq2 contrast/reference" in report
    assert "NA pvalue or padj can occur" in report
    assert "No GO/KEGG/GSEA enrichment analysis is performed." in report
    assert "No complex design" in report
    assert "No batch correction" in report

    lowered_report = report.lower()
    for forbidden_fragment in FORBIDDEN_REPORT_FRAGMENTS:
        assert forbidden_fragment not in lowered_report
