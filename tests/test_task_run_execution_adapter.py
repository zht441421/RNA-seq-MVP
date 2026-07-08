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


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def _assert_no_forbidden_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


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


def _advance_to_qc_ready(client: TestClient, task_id: str) -> None:
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post("/task/qc", json=_qc_payload(task_id)).status_code == 200


def test_task_run_invokes_placeholder_execution_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    client = TestClient(app)
    task_id = _create_task(client)
    _advance_to_qc_ready(client, task_id)

    response = client.post("/task/run", json=_plan_payload(task_id))

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert body["status"] == "run_placeholder_completed"
    assert [artifact["path"] for artifact in body["artifacts"]] == [
        f"tasks/{task_id}/run_summary.json",
        f"tasks/{task_id}/qc_summary.json",
        f"tasks/{task_id}/differential_expression_results.csv",
        f"tasks/{task_id}/report.md",
        f"tasks/{task_id}/run_manifest.json",
        f"tasks/{task_id}/execution_summary.json",
        f"tasks/{task_id}/planned_steps.json",
    ]
    assert all(artifact["executor_name"] == "placeholder_rnaseq_executor" for artifact in body["artifacts"])
    assert [artifact["available"] for artifact in body["artifacts"]] == [
        False,
        False,
        False,
        False,
        True,
        True,
        True,
    ]
    assert (output_root / "tasks" / task_id).is_dir()
    assert sorted(path.name for path in (output_root / "tasks" / task_id).iterdir()) == [
        "execution_summary.json",
        "planned_steps.json",
        "run_manifest.json",
    ]
    _assert_no_forbidden_fragments(body)

    status_response = client.get(f"/task/{task_id}/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "run_placeholder_ready"

    audit_response = client.get(f"/task/{task_id}/audit")
    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert "run_placeholder_executed" in [
        event["event_type"] for event in audit["events"]
    ]
    _assert_no_forbidden_fragments(audit)


def test_unknown_task_id_run_still_returns_deterministic_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))

    response = TestClient(app).post("/task/run", json=_plan_payload("task_missing"))

    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Task not found: task_missing"}
    assert output_root.exists() is False
    _assert_no_forbidden_fragments(body)
