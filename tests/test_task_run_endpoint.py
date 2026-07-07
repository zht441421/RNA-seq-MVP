import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def test_task_run_returns_placeholder_run_result() -> None:
    client = TestClient(app)
    created = client.post("/task/create", json={}).json()
    payload = {
        "task_id": created["task_id"],
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }

    response = client.post("/task/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == created["task_id"]
    assert body["status"] == "run_placeholder_completed"
    assert body["run_steps"]
    assert "artifacts" in body
    assert body["limitations"]
