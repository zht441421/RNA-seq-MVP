import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


FORBIDDEN_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "token",
    "password",
    "secret",
)
FORBIDDEN_BIOLOGICAL_FINDINGS = (
    "pvalue",
    "log2foldchange",
    "gene_symbol",
    "enrichment",
    "pca",
)


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


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


def _qc_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "metadata_file": "metadata.csv",
        "count_matrix_file": "counts.csv",
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _assert_no_public_path_leak(body: object, output_root: Path) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    normalized_text = text.replace("\\\\", "\\").replace("/", "\\")
    assert str(output_root).lower() not in normalized_text
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


def _assert_no_fake_biological_findings(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    assert all(fragment not in text for fragment in FORBIDDEN_BIOLOGICAL_FINDINGS)


def test_task_run_writes_deterministic_dry_run_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    client = TestClient(app)
    task_id = _create_task(client)

    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post("/task/qc", json=_qc_payload(task_id)).status_code == 200

    run_response = client.post("/task/run", json=_plan_payload(task_id))

    assert run_response.status_code == 200
    run_body = run_response.json()
    output_dir = output_root / "tasks" / task_id
    record_paths = {
        "run_manifest.json": output_dir / "run_manifest.json",
        "execution_summary.json": output_dir / "execution_summary.json",
        "planned_steps.json": output_dir / "planned_steps.json",
    }
    assert output_dir.is_dir()
    assert sorted(path.name for path in output_dir.iterdir()) == sorted(record_paths)
    assert all(path.is_file() for path in record_paths.values())

    manifest = json.loads(record_paths["run_manifest.json"].read_text(encoding="utf-8"))
    summary = json.loads(record_paths["execution_summary.json"].read_text(encoding="utf-8"))
    planned_steps = json.loads(record_paths["planned_steps.json"].read_text(encoding="utf-8"))

    assert manifest["task_id"] == task_id
    assert manifest["executor_name"] == "placeholder_rnaseq_executor"
    assert manifest["execution_mode"] == "dry_run"
    assert manifest["omics_type"] == "bulk_rnaseq"
    assert manifest["project_name"] == "demo_bulk_rnaseq"
    assert manifest["output_dir_relative"] == f"tasks/{task_id}"
    assert [entry["relative_path"] for entry in manifest["generated_files"]] == [
        f"tasks/{task_id}/run_manifest.json",
        f"tasks/{task_id}/execution_summary.json",
        f"tasks/{task_id}/planned_steps.json",
    ]

    assert summary["task_id"] == task_id
    assert summary["status"] == "dry_run_completed"
    assert summary["duration_seconds"] == 0.0
    assert summary["real_execution_performed"] is False

    assert [step["step_id"] for step in planned_steps["steps"]] == [
        "validate_inputs",
        "prepare_output_directory",
        "run_quality_control",
        "run_differential_expression",
        "generate_report",
        "collect_artifacts",
    ]
    assert all(step["status"] == "planned_not_executed" for step in planned_steps["steps"])
    assert all(step["external_tool_called"] is False for step in planned_steps["steps"])

    for path in record_paths.values():
        json.loads(path.read_text(encoding="utf-8"))
        _assert_no_fake_biological_findings(path)

    assert [artifact["path"] for artifact in run_body["artifacts"]][-3:] == [
        f"tasks/{task_id}/run_manifest.json",
        f"tasks/{task_id}/execution_summary.json",
        f"tasks/{task_id}/planned_steps.json",
    ]
    assert all(not Path(artifact["path"]).is_absolute() for artifact in run_body["artifacts"])
    _assert_no_public_path_leak(run_body, output_root)


def test_artifacts_endpoint_includes_existing_dry_run_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    client = TestClient(app)
    task_id = _create_task(client)
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post("/task/qc", json=_qc_payload(task_id)).status_code == 200
    assert client.post("/task/run", json=_plan_payload(task_id)).status_code == 200
    assert client.get(f"/task/{task_id}/report").status_code == 200

    artifacts_response = client.get(f"/task/{task_id}/artifacts")

    assert artifacts_response.status_code == 200
    artifacts_body = artifacts_response.json()
    dry_run_artifacts = [
        artifact
        for artifact in artifacts_body["artifacts"]
        if artifact["name"]
        in {"run_manifest.json", "execution_summary.json", "planned_steps.json"}
    ]
    assert [artifact["path"] for artifact in dry_run_artifacts] == [
        f"tasks/{task_id}/run_manifest.json",
        f"tasks/{task_id}/execution_summary.json",
        f"tasks/{task_id}/planned_steps.json",
    ]
    assert all(artifact["available"] is True for artifact in dry_run_artifacts)
    assert all(not Path(artifact["path"]).is_absolute() for artifact in artifacts_body["artifacts"])
    _assert_no_public_path_leak(artifacts_body, output_root)
