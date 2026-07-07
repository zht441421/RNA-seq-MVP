import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def test_task_create_response_can_be_queried_by_status_endpoint() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/task/create",
        json={
            "task_type": "bulk_rnaseq_placeholder",
            "parameters": {
                "project_name": "demo_bulk_rnaseq",
                "omics_type": "bulk_rnaseq",
            },
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["task_id"] == "task_0001"
    assert created["status"] == "created"
    assert "Real RNA-seq analysis is not implemented" in created["message"]

    status_response = client.get(f"/task/{created['task_id']}/status")

    assert status_response.status_code == 200
    status = status_response.json()
    assert status["task_id"] == created["task_id"]
    assert status["status"] == "created"
    assert status["message"] == created["message"]


def test_unknown_task_status_returns_deterministic_404() -> None:
    response = TestClient(app).get("/task/task_missing/status")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found: task_missing"}
