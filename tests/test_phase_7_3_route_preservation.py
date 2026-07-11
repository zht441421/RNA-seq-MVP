from fastapi.testclient import TestClient

from backend.app.main import app


def test_phase_7_3_preserves_existing_routes() -> None:
    client = TestClient(app)
    requests = (
        client.get("/health"),
        client.post("/projects", json={"name": "route preservation"}),
        client.post("/coze/projects", json={"project_name": "route preservation"}),
        client.get("/system/r-env"),
        client.get("/system/docker-r-env"),
        client.get("/ui"),
        client.post("/task/create", json={}),
    )

    assert all(response.status_code != 404 for response in requests)
