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


def test_task_audit_returns_placeholder_audit_trail(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    client = TestClient(app)
    task_id = _create_task(client)
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post("/task/qc", json=_qc_payload(task_id)).status_code == 200
    assert client.post("/task/run", json=_plan_payload(task_id)).status_code == 200
    assert client.get(f"/task/{task_id}/report").status_code == 200
    assert client.get(f"/task/{task_id}/artifacts").status_code == 200

    response = client.get(f"/task/{task_id}/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert body["status"] == "audit_placeholder_ready"
    assert body["events"]
    assert [event["event_id"] for event in body["events"]] == [
        "audit_1",
        "audit_2",
        "audit_3",
        "audit_4",
        "audit_5",
        "audit_6",
    ]
    assert [event["event_type"] for event in body["events"]] == [
        "task_created",
        "plan_generated",
        "qc_checked",
        "run_placeholder_executed",
        "report_placeholder_generated",
        "artifacts_placeholder_listed",
    ]

    required_event_fields = {
        "event_id",
        "event_type",
        "message",
        "timestamp",
        "actor",
        "metadata",
    }
    assert all(required_event_fields <= event.keys() for event in body["events"])
    assert body["limitations"]
