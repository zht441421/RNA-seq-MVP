import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.contracts.coze_tools import build_coze_tool_manifest
from backend.app.main import app
from backend.app.services.task_registry import reset_registry
from backend.app.services.coze_summary import summarize_deseq2_task


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/coze-tool-manifest.json"
DOC = ROOT / "docs/phase-8-2-coze-tool-interface.md"
EXPECTED_TOOLS = {
    "create_analysis_task", "validate_input", "start_analysis",
    "get_task_status", "get_analysis_summary", "list_artifacts",
    "download_artifact",
}
PRESERVED_ROUTES = {
    ("POST", "/task/create"), ("POST", "/task/validate-inputs"),
    ("POST", "/task/{task_id}/inputs/register"), ("POST", "/task/plan"),
    ("POST", "/task/qc"), ("POST", "/task/run"),
    ("GET", "/task/{task_id}/status"), ("GET", "/task/{task_id}/coze-summary"),
    ("GET", "/task/{task_id}/artifacts"),
    ("GET", "/task/{task_id}/artifacts/{artifact_name:path}/download"),
    ("GET", "/task/{task_id}/audit"),
}
FORBIDDEN = ("d:\\", "c:\\", "/home/", "/mnt/", "file://", "traceback", "password=", "token=")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    for name in ("BIOINFO_REQUIRE_API_KEY", "BIOINFO_API_KEY", "RATE_LIMIT_ENABLED", "BIOINFO_MAX_REQUEST_BYTES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "state/tasks.sqlite3"))
    reset_registry()
    yield
    reset_registry()


def _assert_schema_shape(schema: dict) -> None:
    assert schema["type"] in {"object", "string"}
    if schema["type"] == "object":
        assert isinstance(schema.get("properties"), dict)
        assert schema.get("additionalProperties") is False
        assert set(schema.get("required", [])).issubset(schema["properties"])


def test_tool_definitions_have_stable_schemas_and_error_behavior() -> None:
    manifest = build_coze_tool_manifest()
    assert manifest["manifest_version"] == "8.2"
    assert {tool["name"] for tool in manifest["tools"]} == EXPECTED_TOOLS
    for tool in manifest["tools"]:
        assert tool["purpose"]
        assert set(tool["http"]) == {"method", "path", "operation_id"}
        _assert_schema_shape(tool["input_schema"])
        _assert_schema_shape(tool["output_schema"])
        error = tool["error_behavior"]
        assert error["correlation_header"] == "X-Request-ID"
        assert 429 in error["retryable_statuses"]
        assert 401 in error["non_retryable_statuses"]


def test_machine_manifest_is_valid_current_and_documented() -> None:
    stored = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert stored == build_coze_tool_manifest()
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    for tool_name in EXPECTED_TOOLS:
        assert f"`{tool_name}`" in text


def test_tool_bindings_match_openapi_without_removing_routes() -> None:
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    manifest = build_coze_tool_manifest()
    for tool in manifest["tools"]:
        binding = tool["http"]
        operation = schema["paths"][binding["path"]][binding["method"].lower()]
        assert operation["operationId"] == binding["operation_id"]
        assert operation["responses"]
    registered = {(method, route.path) for route in app.routes for method in (route.methods or set())}
    assert PRESERVED_ROUTES.issubset(registered)


def test_tool_routes_preserve_authentication_and_observability(monkeypatch) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", "phase-8-2-key")
    response = TestClient(app).get("/task/task_missing/status")
    assert response.status_code == 401
    assert response.json() == {"detail": "Valid API key required"}
    assert response.headers["x-request-id"]


def test_agent_summary_additions_are_safe_and_backward_compatible() -> None:
    client = TestClient(app)
    created = client.post("/task/create", json={}).json()
    response = client.get(f"/task/{created['task_id']}/coze-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == created["task_id"]
    assert body["status"] == "created"
    assert body["safe_to_present"] is True
    assert body["artifact_references"] == body["result_files"]
    assert body["sanitized_messages"]["summary"] == body["summary_message"]
    assert body["reliability_information"] == {
        "available": False,
        "grade": None,
        "strong_conclusion_allowed": False,
        "guidance": "Use reliability information together with warnings and limitations; do not generate unsupported scientific conclusions.",
    }
    rendered = json.dumps(body).lower()
    assert all(value not in rendered for value in FORBIDDEN)


def test_summary_contract_does_not_turn_results_into_conclusions() -> None:
    summary = summarize_deseq2_task(
        task_id="task_safe",
        status="run_placeholder_ready",
        result_files=[],
        interpretation={"summary": {"top_genes_by_padj": []}},
    )
    assert "biological significance" in summary["interpretation_boundary"].lower()
    assert summary["recommended_next_steps"]


def test_artifact_access_remains_task_scoped_and_safe() -> None:
    client = TestClient(app)
    task_id = client.post("/task/create", json={}).json()["task_id"]
    summary = client.get(f"/task/{task_id}/coze-summary")
    assert summary.status_code == 200
    assert all(
        item["download_url"].startswith(f"/task/{task_id}/artifacts/")
        for item in summary.json()["artifact_references"]
    )
    rejected = client.get(f"/task/{task_id}/artifacts/%2E%2E%2Freport.md/download")
    assert rejected.status_code in {400, 404}
    assert all(value not in rejected.text.lower() for value in FORBIDDEN)
