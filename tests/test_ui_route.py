from fastapi.testclient import TestClient

from backend.app.main import app


def test_ui_route_returns_local_workflow_page() -> None:
    response = TestClient(app).get("/ui")

    assert response.status_code == 200
    assert "Bulk RNA-seq Mock Workflow" in response.text

