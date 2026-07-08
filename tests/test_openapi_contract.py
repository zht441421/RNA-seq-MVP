import json

from fastapi.testclient import TestClient

from backend.app.main import app


EXPECTED_PATH_METHODS = {
    "/health": "get",
    "/task/create": "post",
    "/task/validate-inputs": "post",
    "/task/formal-de/preflight": "get",
    "/task/{task_id}/status": "get",
    "/task/plan": "post",
    "/task/qc": "post",
    "/task/run": "post",
    "/task/{task_id}/report": "get",
    "/task/{task_id}/artifacts": "get",
    "/task/{task_id}/artifacts/{artifact_name}/download": "get",
    "/task/{task_id}/audit": "get",
}

FORBIDDEN_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "secret",
    "token",
    "password",
)


def _assert_no_forbidden_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    leaked_fragments = [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in text]
    assert leaked_fragments == []


def test_openapi_schema_exposes_current_core_endpoints() -> None:
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "paths" in schema

    paths = schema["paths"]
    for path, method in EXPECTED_PATH_METHODS.items():
        assert path in paths
        assert method in paths[path]

    _assert_no_forbidden_fragments(schema)
