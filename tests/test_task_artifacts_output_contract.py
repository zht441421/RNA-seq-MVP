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


def _advance_to_report_ready(client: TestClient, task_id: str) -> None:
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post("/task/qc", json=_qc_payload(task_id)).status_code == 200
    assert client.post("/task/run", json=_plan_payload(task_id)).status_code == 200
    assert client.get(f"/task/{task_id}/report").status_code == 200


def test_task_artifacts_endpoint_exposes_safe_planned_artifact_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    client = TestClient(app)
    task_id = _create_task(client)
    _advance_to_report_ready(client, task_id)

    response = client.get(f"/task/{task_id}/artifacts")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert body["status"] == "artifacts_placeholder_ready"
    assert [artifact["path"] for artifact in body["artifacts"]] == [
        f"tasks/{task_id}/run_summary.json",
        f"tasks/{task_id}/qc_summary.json",
        f"tasks/{task_id}/differential_expression_results.csv",
        f"tasks/{task_id}/report.md",
    ]
    assert all(artifact["available"] is False for artifact in body["artifacts"])
    assert all(not Path(artifact["path"]).is_absolute() for artifact in body["artifacts"])
    assert body["limitations"]
    _assert_no_forbidden_fragments(body)


def test_unknown_task_id_artifacts_output_contract_returns_deterministic_404() -> None:
    response = TestClient(app).get("/task/task_missing/artifacts")

    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Task not found: task_missing"}
    _assert_no_forbidden_fragments(body)
