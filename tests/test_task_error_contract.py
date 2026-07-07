import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


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


def _response_text(body: object) -> str:
    return json.dumps(body, sort_keys=True).lower()


def _assert_no_forbidden_fragments(body: object) -> None:
    text = _response_text(body)
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


def _assert_validation_error_response(response) -> None:
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    _assert_no_forbidden_fragments(body)


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def _create_task(client: TestClient) -> str:
    response = client.post("/task/create", json={})
    assert response.status_code == 200
    return response.json()["task_id"]


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
        "task_id": task_id,
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "metadata_file": "metadata.csv",
        "count_matrix_file": "counts.csv",
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _advance_to_report_ready(client: TestClient, task_id: str) -> None:
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post("/task/qc", json=_qc_payload(task_id)).status_code == 200
    assert client.post("/task/run", json=_plan_payload(task_id)).status_code == 200
    assert client.get(f"/task/{task_id}/report").status_code == 200


@pytest.mark.parametrize(
    ("path", "payload", "missing_field"),
    [
        (
            "/task/plan",
            {"project_name": "demo_bulk_rnaseq"},
            "omics_type",
        ),
        (
            "/task/qc",
            {"project_name": "demo_bulk_rnaseq"},
            "omics_type",
        ),
        (
            "/task/run",
            {
                "project_name": "demo_bulk_rnaseq",
                "omics_type": "bulk_rnaseq",
                "input_level": "count_matrix",
                "analysis_goal": ["qc", "differential_expression"],
                "group_column": "condition",
                "contrast": "treatment_vs_control",
            },
            "task_id",
        ),
    ],
)
def test_missing_required_fields_return_stable_422(
    path: str,
    payload: dict[str, object],
    missing_field: str,
) -> None:
    response = TestClient(app).post(path, json=payload)

    _assert_validation_error_response(response)
    assert any(error["loc"][-1] == missing_field for error in response.json()["detail"])


def test_report_empty_path_segment_does_not_bind_task_id() -> None:
    response = TestClient(app).get("/task//report")

    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Not Found"}
    _assert_no_forbidden_fragments(body)


def test_report_whitespace_task_id_is_routed_deterministically() -> None:
    response = TestClient(app).get("/task/%20/report")

    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Task not found:  "}
    _assert_no_forbidden_fragments(body)


def test_artifacts_and_audit_return_deterministic_placeholder_responses() -> None:
    client = TestClient(app)
    task_id = _create_task(client)
    _advance_to_report_ready(client, task_id)

    artifacts_response = client.get(f"/task/{task_id}/artifacts")
    audit_response = client.get(f"/task/{task_id}/audit")

    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()
    assert artifacts["task_id"] == task_id
    assert artifacts["status"] == "artifacts_placeholder_ready"
    assert [artifact["artifact_id"] for artifact in artifacts["artifacts"]] == [
        "artifact_1",
        "artifact_2",
        "artifact_3",
    ]
    assert all(artifact["path"] is None for artifact in artifacts["artifacts"])
    assert all(artifact["available"] is False for artifact in artifacts["artifacts"])
    _assert_no_forbidden_fragments(artifacts)

    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert audit["task_id"] == task_id
    assert audit["status"] == "audit_placeholder_ready"
    assert [event["event_id"] for event in audit["events"]] == [
        "audit_1",
        "audit_2",
        "audit_3",
        "audit_4",
        "audit_5",
        "audit_6",
    ]
    assert [event["event_type"] for event in audit["events"]] == [
        "task_created",
        "plan_generated",
        "qc_checked",
        "run_placeholder_executed",
        "report_placeholder_generated",
        "artifacts_placeholder_listed",
    ]
    assert all(event["metadata"] == {} for event in audit["events"])
    _assert_no_forbidden_fragments(audit)
