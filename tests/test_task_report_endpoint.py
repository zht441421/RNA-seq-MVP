from fastapi.testclient import TestClient

from backend.app.main import app


def test_task_report_returns_placeholder_report() -> None:
    response = TestClient(app).get("/task/task_demo/report")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "report_placeholder_ready"
    assert body["sections"]
    assert "artifacts" in body
    assert body["limitations"]
