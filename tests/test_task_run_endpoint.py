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
    plan_payload = {
        "task_id": created["task_id"],
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }
    plan_response = client.post("/task/plan", json=plan_payload)
    assert plan_response.status_code == 200

    qc_response = client.post(
        "/task/qc",
        json={
            "task_id": created["task_id"],
            "project_name": "demo_bulk_rnaseq",
            "omics_type": "bulk_rnaseq",
            "input_level": "count_matrix",
            "metadata_file": "metadata.csv",
            "count_matrix_file": "counts.csv",
            "sample_id_column": "sample_id",
            "group_column": "condition",
            "contrast": "treatment_vs_control",
        },
    )
    assert qc_response.status_code == 200

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


def test_task_run_rejects_direct_create_to_run_transition() -> None:
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

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Invalid task status transition: created -> run_placeholder_ready"
    }
