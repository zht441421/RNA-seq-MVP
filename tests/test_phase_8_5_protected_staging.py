import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.contracts.coze_tools import build_coze_tool_manifest
from backend.app.main import app
from backend.app.services.reference_validation import (
    compare_golden_result,
    load_json_object,
    validate_tool_openapi_compatibility,
)
from backend.app.services.task_registry import reset_in_memory_registry, reset_registry
from scripts.verify_phase_8_5_protected_staging import verify_structure


ROOT = Path(__file__).resolve().parents[1]
API_KEY = "phase-8-5-test-key"
HEADERS = {"X-Bioinfo-API-Key": API_KEY}
FORBIDDEN = ("d:\\", "c:\\", "/home/", "/mnt/", "file://", "traceback", API_KEY.lower())


@pytest.fixture(autouse=True)
def protected_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", API_KEY)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str((ROOT / "data/demo").resolve()))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "state/tasks.sqlite3"))
    reset_registry()
    yield
    reset_registry()


def _plan(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "project_name": "phase_8_5_staging",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _run_minimal(client: TestClient, task_id: str) -> None:
    plan = _plan(task_id)
    assert client.post("/task/plan", json=plan, headers=HEADERS).status_code == 200
    assert client.post(
        "/task/qc",
        json={**plan, "metadata_file": "rnaseq_minimal/metadata.csv", "count_matrix_file": "rnaseq_minimal/counts.csv", "sample_id_column": "sample_id"},
        headers=HEADERS,
    ).status_code == 200
    response = client.post(
        "/task/run",
        json={
            **plan,
            "execution_mode": "minimal_real",
            "analysis_method": "minimal_cpm_log2fc",
            "metadata_file": "rnaseq_minimal/metadata.csv",
            "count_matrix_file": "rnaseq_minimal/counts.csv",
            "contrast_column": "condition",
            "contrast_numerator": "treatment",
            "contrast_denominator": "control",
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "minimal_analysis_completed"


def _assert_safe(value: object) -> None:
    rendered = json.dumps(value, sort_keys=True).lower()
    assert all(fragment not in rendered for fragment in FORBIDDEN)


def test_phase_8_5_structure_gate_passes() -> None:
    assert verify_structure() == []


def test_container_boundary_is_local_non_root_persistent_and_secret_backed() -> None:
    compose = (ROOT / "docker-compose.staging.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    nginx = (ROOT / "deploy/staging/nginx.conf").read_text(encoding="utf-8")
    assert '"127.0.0.1:8443:8443"' in compose
    assert "8000:8000" not in compose
    assert "staging_state:/var/lib/bioinfo/state" in compose
    assert "staging_artifacts:/var/lib/bioinfo/artifacts" in compose
    assert "BIOINFO_API_KEY_FILE: /run/secrets/bioinfo_api_key" in compose
    assert "USER 10001:10001" in dockerfile
    assert "return 308 https://localhost:8443$request_uri" in nginx
    assert "$http_x_forwarded" not in nginx.lower()


def test_protected_routes_require_valid_key_and_keep_request_ids() -> None:
    client = TestClient(app)
    for headers in ({}, {"X-Bioinfo-API-Key": "wrong"}):
        response = client.post("/task/create", json={}, headers=headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Valid API key required"}
        assert response.headers["x-request-id"]
        _assert_safe(response.json())
    valid = client.post("/task/create", json={}, headers=HEADERS)
    assert valid.status_code == 200
    assert valid.headers["x-request-id"]


def test_persisted_task_artifacts_and_audit_survive_process_state_reset() -> None:
    client = TestClient(app)
    task_id = client.post("/task/create", json={}, headers=HEADERS).json()["task_id"]
    _run_minimal(client, task_id)
    before = client.get(f"/task/{task_id}/artifacts", headers=HEADERS).json()
    assert before["artifacts"]
    reset_in_memory_registry()
    status = client.get(f"/task/{task_id}/status", headers=HEADERS)
    artifacts = client.get(f"/task/{task_id}/artifacts", headers=HEADERS)
    audit = client.get(f"/task/{task_id}/audit", headers=HEADERS)
    assert status.status_code == artifacts.status_code == audit.status_code == 200
    assert status.json()["status"] == "run_placeholder_ready"
    assert artifacts.json() == before
    assert "minimal_rnaseq_executed" in {event["event_type"] for event in audit.json()["events"]}
    report = client.get(f"/task/{task_id}/artifacts/report.md/download", headers=HEADERS)
    assert report.status_code == 200
    for body in (status.json(), artifacts.json(), audit.json()):
        _assert_safe(body)


def test_artifact_access_remains_task_scoped_and_rejects_traversal() -> None:
    client = TestClient(app)
    source = client.post("/task/create", json={}, headers=HEADERS).json()["task_id"]
    other = client.post("/task/create", json={}, headers=HEADERS).json()["task_id"]
    _run_minimal(client, source)
    cross_task = client.get(f"/task/{other}/artifacts/report.md/download", headers=HEADERS)
    traversal = client.get(f"/task/{source}/artifacts/%2E%2E%2Freport.md/download", headers=HEADERS)
    assert cross_task.status_code == 404
    assert traversal.status_code in {400, 404}
    _assert_safe(cross_task.json())
    _assert_safe(traversal.json())


def test_agent_summary_preserves_reliability_and_scientific_boundary() -> None:
    client = TestClient(app)
    task_id = client.post("/task/create", json={}, headers=HEADERS).json()["task_id"]
    _run_minimal(client, task_id)
    summary = client.get(f"/task/{task_id}/coze-summary", headers=HEADERS).json()
    assert summary["reliability_information"]["strong_conclusion_allowed"] is False
    assert summary["safe_to_present"] is True
    assert "exploratory" in summary["interpretation_boundary"].lower()
    rendered = json.dumps(summary).lower()
    assert "p-value" not in rendered or "no p-value" in rendered
    _assert_safe(summary)


def test_golden_result_and_all_seven_tool_bindings_remain_compatible() -> None:
    manifest = build_coze_tool_manifest()
    assert len(manifest["tools"]) == 7
    assert validate_tool_openapi_compatibility(manifest, app.openapi()) == []
    golden = load_json_object(ROOT / "docs/reference-datasets/golden-results/phase-8-4-rnaseq-minimal-synthetic-v1.json")
    checks = golden["checks"]
    observation = {
        **checks["exact"],
        "input_gene_count": checks["numeric_ranges"]["input_gene_count"]["min"],
        "reliability_information": {"available": False, "grade": None, "strong_conclusion_allowed": False},
        "warnings": [], "limitations": [],
        "interpretation_boundary": "Exploratory output only.",
        "summary_fields": golden["expected_summary_schema_fields"],
        "artifact_categories": checks["required_artifact_categories"],
        "claims": [], "deseq2_execution_state": "unavailable",
    }
    assert compare_golden_result(observation, golden, environment={"deseq2_ready": False})["passed"] is True


def test_phase_8_5_runbook_records_non_goals_and_restart_limitations() -> None:
    text = (ROOT / "docs/phase-8-5-protected-staging-deployment.md").read_text(encoding="utf-8").lower()
    for statement in (
        "no remote deployment", "no automatic resume", "execution trace entries and rate limit counters",
        "does not prove scientific validity", "phase 8.6", "phase 8.7",
    ):
        assert statement in text
