import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "backend/app/contracts/coze_integration_manifest.json"
EXPECTED = {
    "coze_create_analysis_task": ("post", "/task/create"),
    "coze_register_analysis_input": ("post", "/task/{task_id}/inputs/register"),
    "coze_validate_analysis_inputs": ("post", "/task/validate-inputs"),
    "coze_run_analysis_task": ("post", "/task/run"),
    "coze_query_task_status": ("get", "/task/{task_id}/status"),
    "coze_list_task_artifacts": ("get", "/task/{task_id}/artifacts"),
    "coze_retrieve_result_summary": ("get", "/task/{task_id}/coze-summary"),
}
FORBIDDEN = ("d:\\", "c:\\", "/home/", "/mnt/", "file://", "traceback", "password=")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in ("BIOINFO_REQUIRE_API_KEY", "BIOINFO_API_KEY", "RATE_LIMIT_ENABLED", "BIOINFO_MAX_REQUEST_BYTES"):
        monkeypatch.delenv(name, raising=False)
    reset_registry()
    yield
    reset_registry()


def test_manifest_operations_match_valid_described_openapi_operations() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    assert len(manifest["operations"]) == len(EXPECTED)
    for operation in manifest["operations"]:
        operation_id = operation["operation_id"]
        method, path = EXPECTED[operation_id]
        described = schema["paths"][path][method]
        assert described["operationId"] == operation_id
        assert described["summary"]
        assert described["description"]
        assert described["x-coze-operation"] == operation["name"]
        assert "responses" in described


def test_existing_routes_remain_registered() -> None:
    paths = {(route.path, method) for route in app.routes for method in (route.methods or set())}
    for method, path in EXPECTED.values():
        assert (path, method.upper()) in paths
    assert len(app.routes) == 39


def test_authentication_and_observability_remain_active(monkeypatch) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", "phase-8-1-key")
    response = TestClient(app).post("/task/create", json={})
    assert response.status_code == 401
    assert response.json() == {"detail": "Valid API key required"}
    assert response.headers["x-request-id"]


def test_artifact_access_remains_task_scoped_and_safe(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    client = TestClient(app)
    task_id = client.post("/task/create", json={}).json()["task_id"]
    response = client.get(f"/task/{task_id}/artifacts/%2E%2E%2Freport.md/download")
    assert response.status_code in {400, 404}
    rendered = response.text.lower()
    assert all(fragment not in rendered for fragment in FORBIDDEN)


def test_existing_summary_layer_is_concise_and_non_conclusive() -> None:
    client = TestClient(app)
    task_id = client.post("/task/create", json={}).json()["task_id"]
    response = client.get(f"/task/{task_id}/coze-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert body["status"] == "created"
    assert body["safe_to_present"] is True
    assert body["result_files"]
    assert body["limitations"]
    assert "conclusion" in body["interpretation_boundary"].lower()
