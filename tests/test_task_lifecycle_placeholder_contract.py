import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


TASK_ID = "task_demo"


def _plan_payload() -> dict[str, object]:
    return {
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _qc_payload() -> dict[str, object]:
    return {
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "metadata_file": "metadata.csv",
        "count_matrix_file": "counts.csv",
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _run_payload() -> dict[str, object]:
    payload = _plan_payload()
    payload["task_id"] = TASK_ID
    return payload


def _phase_2_lifecycle_responses(client: TestClient) -> dict[str, dict[str, object]]:
    responses = {
        "plan": client.post("/task/plan", json=_plan_payload()),
        "qc": client.post("/task/qc", json=_qc_payload()),
        "run": client.post("/task/run", json=_run_payload()),
        "report": client.get(f"/task/{TASK_ID}/report"),
        "artifacts": client.get(f"/task/{TASK_ID}/artifacts"),
        "audit": client.get(f"/task/{TASK_ID}/audit"),
    }

    bodies: dict[str, dict[str, object]] = {}
    for endpoint, response in responses.items():
        assert response.status_code == 200, endpoint
        bodies[endpoint] = response.json()
    return bodies


def _response_text(body: dict[str, object]) -> str:
    return json.dumps(body, sort_keys=True).lower()


def _assert_no_runtime_leaks(body: dict[str, object]) -> None:
    text = _response_text(body)
    forbidden_fragments = (
        "d:\\",
        "c:\\",
        "/home/",
        "/mnt/",
        "traceback",
        "secret",
        "token",
        "password",
    )
    assert all(fragment not in text for fragment in forbidden_fragments)

    real_execution_claims = (
        "real rna-seq pipeline ran",
        "real rna-seq pipeline completed",
        "rna-seq pipeline ran",
        "rna-seq pipeline completed",
        "production run completed",
    )
    assert all(claim not in text for claim in real_execution_claims)


def test_phase_2_placeholder_lifecycle_responses_are_bounded() -> None:
    bodies = _phase_2_lifecycle_responses(TestClient(app))

    expected_payload_fields = {
        "plan": "recommended_workflow",
        "qc": "qc_checks",
        "run": "run_steps",
        "report": "sections",
        "artifacts": "artifacts",
        "audit": "events",
    }
    for endpoint, payload_field in expected_payload_fields.items():
        body = bodies[endpoint]
        assert payload_field in body
        assert body[payload_field] is not None

        text = _response_text(body)
        assert any(marker in text for marker in ("placeholder", "skeleton"))
        assert any(marker in text for marker in ("no real", "not implemented", "does not"))
        _assert_no_runtime_leaks(body)


def test_current_task_id_echo_scope_is_documented() -> None:
    bodies = _phase_2_lifecycle_responses(TestClient(app))

    assert "task_id" not in bodies["plan"]
    assert "task_id" not in bodies["qc"]
    assert bodies["run"]["task_id"] == TASK_ID
    assert bodies["report"]["task_id"] == TASK_ID
    assert bodies["artifacts"]["task_id"] == TASK_ID
    assert bodies["audit"]["task_id"] == TASK_ID


@pytest.mark.xfail(
    strict=True,
    reason="Plan and QC response models do not yet echo task_id in the Phase 2 skeleton.",
)
def test_all_phase_2_lifecycle_endpoints_echo_task_id_contract() -> None:
    bodies = _phase_2_lifecycle_responses(TestClient(app))

    for body in bodies.values():
        assert body["task_id"] == TASK_ID
