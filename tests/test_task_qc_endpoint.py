import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def test_task_qc_returns_placeholder_qc_plan() -> None:
    client = TestClient(app)
    created = client.post("/task/create", json={}).json()
    plan_response = client.post(
        "/task/plan",
        json={
            "task_id": created["task_id"],
            "project_name": "demo_bulk_rnaseq",
            "omics_type": "bulk_rnaseq",
            "input_level": "count_matrix",
            "analysis_goal": ["qc", "differential_expression"],
            "group_column": "condition",
            "contrast": "treatment_vs_control",
        },
    )
    assert plan_response.status_code == 200

    payload = {
        "task_id": created["task_id"],
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "metadata_file": "metadata.csv",
        "count_matrix_file": "counts.csv",
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }

    response = client.post("/task/qc", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == created["task_id"]
    assert body["status"] == "qc_planned"
    assert body["qc_checks"]
    assert body["reliability_gates"]
    assert body["limitations"]

    legacy_payload = dict(payload)
    legacy_payload.pop("task_id")
    legacy_response = client.post("/task/qc", json=legacy_payload)

    assert legacy_response.status_code == 200
    assert "task_id" not in legacy_response.json()


def test_task_qc_rejects_direct_create_to_qc_transition() -> None:
    client = TestClient(app)
    created = client.post("/task/create", json={}).json()
    payload = {
        "task_id": created["task_id"],
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "metadata_file": "metadata.csv",
        "count_matrix_file": "counts.csv",
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }

    response = client.post("/task/qc", json=payload)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Invalid task status transition: created -> qc_placeholder_ready"
    }
