from fastapi.testclient import TestClient

from backend.app.main import app


def test_task_audit_returns_placeholder_audit_trail() -> None:
    response = TestClient(app).get("/task/task_demo/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task_demo"
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
