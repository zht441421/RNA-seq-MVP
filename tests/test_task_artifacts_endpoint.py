from fastapi.testclient import TestClient

from backend.app.main import app


def test_task_artifacts_returns_placeholder_artifacts() -> None:
    response = TestClient(app).get("/task/task_demo/artifacts")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "artifacts_placeholder_ready"
    assert body["artifacts"]
    assert all(artifact["available"] is False for artifact in body["artifacts"])
    assert body["limitations"]
