import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def test_task_plan_returns_placeholder_analysis_plan() -> None:
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

    response = client.post("/task/plan", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == created["task_id"]
    assert body["project_name"] == "demo_bulk_rnaseq"
    assert body["omics_type"] == "bulk_rnaseq"
    assert body["input_level"] == "count_matrix"
    assert body["status"] == "planned"
    assert body["recommended_workflow"]
    assert body["reliability_notes"]

    legacy_payload = dict(payload)
    legacy_payload.pop("task_id")
    legacy_response = client.post("/task/plan", json=legacy_payload)

    assert legacy_response.status_code == 200
    assert "task_id" not in legacy_response.json()
