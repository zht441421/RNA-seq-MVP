import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import deseq2_execution
from backend.app.services.formal_de_preflight import CommandResult
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


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def _assert_no_forbidden_public_fragments(body: object) -> None:
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
                "GeneA,100,120,250,260",
                "GeneB,20,22,10,12",
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
        "execution_mode": "formal_de_real",
        "analysis_method": "deseq2",
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


def _not_ready_preflight() -> dict:
    return {
        "ready": False,
        "r_available": False,
        "rscript_available": False,
        "biocmanager_available": False,
        "deseq2_available": False,
        "warnings": [],
        "limitations": [
            "DESeq2 execution is not available until R, Rscript, BiocManager, and DESeq2 are installed."
        ],
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


def test_task_run_deseq2_preflight_not_ready_is_safe_and_not_completed(
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
        _not_ready_preflight,
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        deseq2_execution,
        "run_command_safely",
        lambda args, timeout_seconds=120: calls.append(args) or CommandResult(args=args, returncode=0),
    )

    client = TestClient(app)
    task_id = _create_ready_task(client, metadata_file, count_matrix_file)
    response = client.post(
        "/task/run",
        json=_run_payload(task_id, metadata_file, count_matrix_file),
    )

    assert response.status_code == 501
    body = response.json()
    assert body["detail"]["error_code"] == "DESEQ2_PREFLIGHT_NOT_READY"
    assert (
        body["detail"]["message"]
        == "DESeq2 execution is not available because the preflight check is not ready."
    )
    assert calls == []
    assert not (output_root / "tasks" / task_id / "deseq2_results.csv").exists()
    assert client.get(f"/task/{task_id}/status").json()["status"] == "qc_placeholder_ready"
    task = get_task(task_id)
    assert task is not None
    assert "deseq2_executed" not in [event.event_type for event in task.lifecycle_events]
    _assert_no_forbidden_public_fragments(body)


def test_task_run_deseq2_success_returns_artifacts(
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

    def fake_run(args: list[str], timeout_seconds: int = 120) -> CommandResult:
        _write_mock_results(args[-1])
        return CommandResult(args=args, returncode=0)

    monkeypatch.setattr(deseq2_execution, "run_command_safely", fake_run)

    client = TestClient(app)
    task_id = _create_ready_task(client, metadata_file, count_matrix_file)
    response = client.post(
        "/task/run",
        json=_run_payload(task_id, metadata_file, count_matrix_file),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "deseq2_analysis_completed"
    artifact_names = [artifact["name"] for artifact in body["artifacts"]]
    assert artifact_names == [
        "deseq2_results.csv",
        "deseq2_summary.json",
        "deseq2_run_manifest.json",
        "report.md",
    ]
    assert all(artifact["available"] is True for artifact in body["artifacts"])
    assert client.get(f"/task/{task_id}/status").json()["status"] == "run_placeholder_ready"
    _assert_no_forbidden_public_fragments(body)
