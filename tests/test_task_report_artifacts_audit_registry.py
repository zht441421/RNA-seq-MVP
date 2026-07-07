import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


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


def test_report_artifacts_and_audit_are_registry_backed() -> None:
    client = TestClient(app)
    task_id = _create_task(client)

    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post("/task/qc", json=_qc_payload(task_id)).status_code == 200
    assert client.post("/task/run", json=_plan_payload(task_id)).status_code == 200

    report_response = client.get(f"/task/{task_id}/report")

    assert report_response.status_code == 200
    assert report_response.json()["status"] == "report_placeholder_ready"
    _assert_status(client, task_id, "report_placeholder_ready")

    artifacts_response = client.get(f"/task/{task_id}/artifacts")

    assert artifacts_response.status_code == 200
    assert artifacts_response.json()["status"] == "artifacts_placeholder_ready"
    _assert_status(client, task_id, "artifacts_placeholder_ready")

    audit_response = client.get(f"/task/{task_id}/audit")

    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert audit["task_id"] == task_id
    assert audit["status"] == "audit_placeholder_ready"
    assert [event["event_type"] for event in audit["events"]] == [
        "task_created",
        "plan_generated",
        "qc_checked",
        "run_placeholder_executed",
        "report_placeholder_generated",
        "artifacts_placeholder_listed",
    ]

    second_audit_response = client.get(f"/task/{task_id}/audit")
    assert second_audit_response.status_code == 200
    assert second_audit_response.json() == audit
    _assert_status(client, task_id, "artifacts_placeholder_ready")
