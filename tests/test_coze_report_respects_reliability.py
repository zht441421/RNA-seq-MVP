from fastapi.testclient import TestClient

from backend.app.main import app
from tests.test_coze_confirm_and_run_mock import prepare
from tests.test_coze_prepare_analysis import create_inspected_project


def test_coze_report_respects_grade_c_reliability() -> None:
    client = TestClient(app)
    project_id = create_inspected_project(client)
    prepare(client, project_id)
    client.post(
        f"/coze/projects/{project_id}/confirm-and-run",
        json={"confirmed": True, "run_mode": "mock", "analysis_plan_overrides": {}},
    ).raise_for_status()

    response = client.get(f"/coze/projects/{project_id}/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strong_conclusion_allowed"] is False
    assert payload["allowed_conclusion_level"] == "Exploratory findings only."
    assert "Current evidence is not sufficient for a strong scientific conclusion." in payload["summary_markdown"]
    assert payload["artifact_manifest"]["project_id"] == project_id
    assert payload["audit_log"]["reliability"]["grade"] == "C"

