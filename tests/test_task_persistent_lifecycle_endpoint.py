import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import (
    list_task_artifacts,
    reset_in_memory_registry,
    reset_registry,
)


FORBIDDEN_PUBLIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "token",
    "password",
    "secret",
)


def _assert_no_forbidden_public_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    for forbidden_fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert forbidden_fragment not in text


def _plan_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _qc_payload(task_id: str) -> dict[str, object]:
    return {
        **_plan_payload(task_id),
        "metadata_file": "metadata.csv",
        "count_matrix_file": "counts.csv",
        "sample_id_column": "sample_id",
    }


def test_task_lifecycle_survives_registry_reinitialization_through_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    reset_registry()
    client = TestClient(app)

    create_response = client.post(
        "/task/create",
        json={
            "task_type": "bulk_rnaseq_placeholder",
            "parameters": {"project_name": "demo_bulk_rnaseq"},
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    task_id = created["task_id"]
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200

    reset_in_memory_registry()

    status_response = client.get(f"/task/{task_id}/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "planned"

    audit_response = client.get(f"/task/{task_id}/audit")
    assert audit_response.status_code == 200
    audit_body = audit_response.json()
    assert [event["event_type"] for event in audit_body["events"]] == [
        "task_created",
        "plan_generated",
    ]

    for body in (created, status_response.json(), audit_body):
        _assert_no_forbidden_public_fragments(body)
        assert str(tmp_path).lower() not in json.dumps(body, sort_keys=True).lower()
    reset_registry()


def test_artifacts_endpoint_persists_safe_relative_artifact_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(tmp_path / "outputs"))
    reset_registry()
    client = TestClient(app)
    task_id = client.post("/task/create", json={}).json()["task_id"]
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post("/task/qc", json=_qc_payload(task_id)).status_code == 200
    assert client.post("/task/run", json=_plan_payload(task_id)).status_code == 200
    assert client.get(f"/task/{task_id}/report").status_code == 200

    response = client.get(f"/task/{task_id}/artifacts")

    assert response.status_code == 200
    body = response.json()
    artifacts = list_task_artifacts(task_id)
    assert artifacts
    assert all(
        artifact["safe_relative_path"].startswith(f"tasks/{task_id}/")
        for artifact in artifacts
    )
    _assert_no_forbidden_public_fragments(body)
    _assert_no_forbidden_public_fragments(artifacts)
    reset_registry()
