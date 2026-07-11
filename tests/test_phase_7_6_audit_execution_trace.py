import json
import re

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.execution_trace import list_execution_traces
from backend.app.services.task_registry import get_task, reset_registry


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in ("BIOINFO_REQUIRE_API_KEY", "BIOINFO_API_KEY", "BIOINFO_MAX_REQUEST_BYTES", "RATE_LIMIT_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    reset_registry()
    yield
    reset_registry()


def _create(client):
    response = client.post("/task/create", json={"task_type": "bulk_rnaseq_placeholder", "parameters": {"omics_type": "bulk_rnaseq"}})
    assert response.status_code == 200
    return response.json()["task_id"], response.headers["x-request-id"]


def _plan(task_id):
    return {"task_id": task_id, "project_name": "trace-test", "omics_type": "bulk_rnaseq", "input_level": "count_matrix", "analysis_goal": ["differential_expression"], "group_column": "condition", "contrast": "treatment_vs_control"}


def _qc(task_id):
    return {**_plan(task_id), "metadata_file": "metadata.csv", "count_matrix_file": "counts.csv", "sample_id_column": "sample_id"}


def _advance(client, task_id):
    assert client.post("/task/plan", json=_plan(task_id)).status_code == 200
    assert client.post("/task/qc", json=_qc(task_id)).status_code == 200


def test_trace_metadata_generated_and_linked(tmp_path, monkeypatch):
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    client = TestClient(app)
    task_id, request_id = _create(client)
    assert list_execution_traces(task_id)[0]["request_id"] == request_id
    _advance(client, task_id)
    response = client.post("/task/run", json=_plan(task_id))
    assert response.status_code == 200
    trace = list_execution_traces(task_id)[-1]
    assert re.fullmatch(r"[0-9a-f]{32}", trace["trace_id"])
    assert trace["request_id"] == response.headers["x-request-id"]
    assert trace["task_id"] == task_id
    assert trace["execution_start_timestamp"] and trace["execution_end_timestamp"]
    assert trace["duration_seconds"] >= 0 and trace["execution_status"] == "completed"
    assert trace["analysis_version"] == "phase-7.6"
    assert trace["runner_version"] == "execution-trace-v1"
    assert trace["configuration_snapshot_id"].startswith("sha256:")
    assert trace["runtime_metadata"]["metadata_status"] == "placeholder"


def test_lifecycle_names_preserved_and_trace_added(tmp_path, monkeypatch):
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    client = TestClient(app)
    task_id, _ = _create(client)
    _advance(client, task_id)
    assert client.post("/task/run", json=_plan(task_id)).status_code == 200
    assert client.get(f"/task/{task_id}/report").status_code == 200
    assert client.get(f"/task/{task_id}/artifacts").status_code == 200
    task = get_task(task_id)
    assert [event.event_type for event in task.lifecycle_events] == ["task_created", "plan_generated", "qc_checked", "run_placeholder_executed", "report_placeholder_generated", "artifacts_placeholder_listed"]
    run_event = next(event for event in task.lifecycle_events if event.event_type == "run_placeholder_executed")
    assert run_event.metadata == {}
    assert list_execution_traces(task_id)[-1]["execution_status"] == "completed"


def test_failure_trace_is_sanitized_and_correlated(tmp_path, monkeypatch):
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    client = TestClient(app)
    task_id, _ = _create(client)
    _advance(client, task_id)

    def fail_with_private_detail(**kwargs):
        raise ValueError("C:\\private\\secret token=password")

    monkeypatch.setattr("backend.app.api.task_routes.execute_task_placeholder", fail_with_private_detail)
    response = client.post("/task/run", json=_plan(task_id))
    assert response.status_code == 400
    assert response.json() == {"detail": "Placeholder execution failed."}
    trace = list_execution_traces(task_id)[-1]
    assert trace["execution_status"] == "failed"
    assert trace["failure_reason"] == "execution_failed"
    assert trace["request_id"] == response.headers["x-request-id"]
    failed_event = get_task(task_id).lifecycle_events[-1]
    assert failed_event.event_type == "analysis_failed"
    assert failed_event.metadata["execution_trace"]["trace_id"] == trace["trace_id"]
    assert all(word not in json.dumps(failed_event.metadata).lower() for word in ("private", "password", "token"))


def test_routes_security_and_observability_preserved(monkeypatch):
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/system/r-env").status_code != 404
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", "phase-7-6-key")
    auth = client.post("/task/create", json={})
    assert auth.status_code == 401 and auth.headers["x-request-id"]
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", "10")
    oversized = client.post("/task/create", json={"value": "x" * 100})
    assert oversized.status_code == 413 and oversized.headers["x-request-id"]
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", "0")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    assert client.get("/system/docker-r-env").status_code == 200
    limited = client.get("/system/docker-r-env")
    assert limited.status_code == 429 and limited.headers["x-request-id"]
