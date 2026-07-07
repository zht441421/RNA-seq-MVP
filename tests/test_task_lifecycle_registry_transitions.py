import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import get_task, reset_registry


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def _create_task(client: TestClient) -> str:
    response = client.post(
        "/task/create",
        json={
            "task_type": "bulk_rnaseq_placeholder",
            "parameters": {
                "project_name": "demo_bulk_rnaseq",
                "omics_type": "bulk_rnaseq",
            },
        },
    )
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


def _assert_status(client: TestClient, task_id: str, expected_status: str) -> None:
    response = client.get(f"/task/{task_id}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert body["status"] == expected_status


def test_plan_qc_run_update_registry_status_and_lifecycle_events() -> None:
    client = TestClient(app)
    task_id = _create_task(client)

    plan_response = client.post("/task/plan", json=_plan_payload(task_id))
    assert plan_response.status_code == 200
    _assert_status(client, task_id, "planned")

    qc_response = client.post("/task/qc", json=_qc_payload(task_id))
    assert qc_response.status_code == 200
    _assert_status(client, task_id, "qc_placeholder_ready")

    run_response = client.post("/task/run", json=_plan_payload(task_id))
    assert run_response.status_code == 200
    _assert_status(client, task_id, "run_placeholder_ready")

    task = get_task(task_id)
    assert task is not None
    assert task.updated_at == "2026-01-01T00:00:03Z"
    assert [event.event_type for event in task.lifecycle_events] == [
        "task_created",
        "plan_generated",
        "qc_checked",
        "run_placeholder_executed",
    ]
    assert task.lifecycle_events[1].message == (
        "Placeholder analysis plan generated and task status updated."
    )
    assert task.lifecycle_events[2].message == (
        "Placeholder QC checks generated and task status updated."
    )
    assert task.lifecycle_events[3].message == (
        "Placeholder run executed and task status updated. "
        "No real RNA-seq analysis was performed."
    )
    assert all(event.actor == "system" for event in task.lifecycle_events)
