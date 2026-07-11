import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.contracts.coze_tools import build_coze_tool_manifest
from backend.app.main import app
from backend.app.services.local_agent_simulator import LocalAgentSimulator
from backend.app.services.execution_trace import list_execution_traces
from backend.app.services.task_registry import reset_registry


ROOT = Path(__file__).resolve().parents[1]
DEMO_METADATA = "rnaseq_minimal/metadata.csv"
DEMO_COUNTS = "rnaseq_minimal/counts.csv"
FORBIDDEN = ("d:\\", "c:\\", "/home/", "/mnt/", "file://", "traceback", "password=", "token=", "secret=")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    for name in ("BIOINFO_REQUIRE_API_KEY", "BIOINFO_API_KEY", "RATE_LIMIT_ENABLED", "BIOINFO_MAX_REQUEST_BYTES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str((ROOT / "data/demo").resolve()))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "state/tasks.sqlite3"))
    reset_registry()
    yield
    reset_registry()


def _request() -> dict:
    return {
        "project_name": "phase_8_3_local_agent",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "metadata_file": DEMO_METADATA,
        "count_matrix_file": DEMO_COUNTS,
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast_numerator": "treatment",
        "contrast_denominator": "control",
        "execution_mode": "minimal_real",
        "analysis_method": "minimal_cpm_log2fc",
        "max_status_polls": 3,
    }


def _assert_public_safe(payload: object) -> None:
    rendered = json.dumps(payload, sort_keys=True).lower()
    assert all(fragment not in rendered for fragment in FORBIDDEN)


def test_agent_request_selection_uses_only_manifest_tools() -> None:
    simulator = LocalAgentSimulator(TestClient(app))
    expected = {
        "create task": "create_analysis_task",
        "validate input": "validate_input",
        "start analysis": "start_analysis",
        "check status": "get_task_status",
        "get summary": "get_analysis_summary",
        "list artifacts": "list_artifacts",
        "download artifact": "download_artifact",
    }
    manifest_names = {tool["name"] for tool in build_coze_tool_manifest()["tools"]}
    assert set(expected.values()) == manifest_names
    for request, tool_name in expected.items():
        assert simulator.select_tool(request) == tool_name


def test_tool_invocations_cover_complete_agent_facing_sequence() -> None:
    simulator = LocalAgentSimulator(TestClient(app))
    result = simulator.simulate_workflow(_request())

    assert result["completed"] is True
    invoked = [step["tool_name"] for step in result["steps"]]
    for tool_name in (
        "create_analysis_task",
        "validate_input",
        "start_analysis",
        "get_task_status",
        "get_analysis_summary",
        "list_artifacts",
    ):
        assert tool_name in invoked
    assert all(step["request_id"] for step in result["steps"])
    _assert_public_safe(result)


def test_end_to_end_local_agent_workflow_preserves_scientific_boundaries() -> None:
    client = TestClient(app)
    simulator = LocalAgentSimulator(client)
    result = simulator.simulate_workflow(_request())

    assert result["completed"] is True
    assert result["scientific_conclusion_generated"] is False
    assert result["summary"]["analysis_method"] == "minimal_cpm_log2fc"
    assert result["summary"]["statistical_test_performed"] is False
    assert result["summary"]["safe_to_present"] is True
    assert "exploratory" in result["summary"]["interpretation_boundary"].lower()
    assert result["reliability_information"] == result["summary"]["reliability_information"]
    assert result["reliability_information"]["available"] is False
    assert result["reliability_information"]["strong_conclusion_allowed"] is False
    assert result["artifacts"]["task_id"] == result["task_id"]
    assert all(item["available"] for item in result["artifacts"]["artifacts"])
    assert all(not Path(item["path"]).is_absolute() for item in result["artifacts"]["artifacts"])
    audit = client.get(f"/task/{result['task_id']}/audit")
    assert audit.status_code == 200
    event_types = [event["event_type"] for event in audit.json()["events"]]
    assert event_types[:3] == [
        "task_created",
        "task_input_registered",
        "task_input_registered",
    ]
    assert "minimal_rnaseq_executed" in event_types
    trace = list_execution_traces(result["task_id"])[-1]
    assert trace["execution_status"] == "completed"
    assert trace["request_id"]
    _assert_public_safe(result)


def test_failures_are_structured_and_do_not_expose_internal_details() -> None:
    simulator = LocalAgentSimulator(TestClient(app))
    unsupported = simulator.handle_request("write a conclusion", {})
    missing = simulator.invoke_tool("get_task_status", {})
    unknown_task = simulator.invoke_tool("get_task_status", {"task_id": "task_missing"})
    invalid_workflow = simulator.simulate_workflow({})

    assert unsupported["error"]["code"] == "UNSUPPORTED_AGENT_REQUEST"
    assert missing["error"]["code"] == "INVALID_TOOL_ARGUMENTS"
    assert unknown_task["status_code"] == 404
    assert unknown_task["error"]["code"] == "TOOL_HTTP_ERROR"
    assert invalid_workflow["completed"] is False
    assert invalid_workflow["steps"][0]["error"]["code"] == "INVALID_WORKFLOW_REQUEST"
    for payload in (unsupported, missing, unknown_task):
        assert payload["ok"] is False
        _assert_public_safe(payload)
    _assert_public_safe(invalid_workflow)


def test_authentication_remains_enforced_for_simulated_tools(monkeypatch) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", "phase-8-3-local-key")
    result = LocalAgentSimulator(TestClient(app)).invoke_tool("create_analysis_task", {})

    assert result["ok"] is False
    assert result["status_code"] == 401
    assert result["request_id"]
    assert result["error"]["detail"] == "Valid API key required"


def test_download_tool_uses_only_task_scoped_artifact_name() -> None:
    simulator = LocalAgentSimulator(TestClient(app))
    workflow = simulator.simulate_workflow(_request())
    report = next(item for item in workflow["artifacts"]["artifacts"] if item["name"] == "report.md")
    downloaded = simulator.invoke_tool(
        "download_artifact",
        {"task_id": workflow["task_id"], "artifact_name": report["name"]},
    )
    traversal = simulator.invoke_tool(
        "download_artifact",
        {"task_id": workflow["task_id"], "artifact_name": "../report.md"},
    )

    assert downloaded["ok"] is True
    assert downloaded["data"]["size_bytes"] > 0
    assert "report.md" in downloaded["data"]["content_disposition"]
    assert traversal["ok"] is False
    assert traversal["status_code"] in {400, 404}
    _assert_public_safe({"downloaded": downloaded, "traversal": traversal})
