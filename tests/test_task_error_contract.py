import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


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

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == " "
    assert body["status"] == "report_placeholder_ready"
    assert body["sections"]
    assert body["limitations"]
    _assert_no_forbidden_fragments(body)


def test_artifacts_and_audit_return_deterministic_placeholder_responses() -> None:
    client = TestClient(app)

    artifacts_response = client.get("/task/task_demo/artifacts")
    audit_response = client.get("/task/task_demo/audit")

    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()
    assert artifacts["task_id"] == "task_demo"
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
    assert audit["task_id"] == "task_demo"
    assert audit["status"] == "audit_placeholder_ready"
    assert [event["event_id"] for event in audit["events"]] == [
        "audit_1",
        "audit_2",
        "audit_3",
        "audit_4",
        "audit_5",
        "audit_6",
    ]
    assert all(event["metadata"] == {} for event in audit["events"])
    _assert_no_forbidden_fragments(audit)
