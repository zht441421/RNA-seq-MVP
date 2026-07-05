from fastapi.testclient import TestClient

from backend.app.main import app
from tests.test_coze_prepare_analysis import create_inspected_project


def prepare(client: TestClient, project_id: str) -> None:
    client.post(
        f"/coze/projects/{project_id}/prepare-analysis",
        json={
            "gene_id_column": "gene_id",
            "sample_id_column": "sample_id",
            "group_column": "condition",
            "reference_group": "control",
            "test_group": "treatment",
            "batch_column": None,
            "covariates": [],
            "fdr_threshold": 0.05,
            "log2fc_threshold": 1.0,
        },
    ).raise_for_status()


def test_coze_confirm_and_run_mock_returns_manifest() -> None:
    client = TestClient(app)
    project_id = create_inspected_project(client)
    prepare(client, project_id)

    response = client.post(
        f"/coze/projects/{project_id}/confirm-and-run",
        json={"confirmed": True, "run_mode": "mock", "analysis_plan_overrides": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_status"] == "completed"
    assert payload["reliability_grade"] == "C"
    assert payload["artifact_manifest"]["project_id"] == project_id
    assert payload["artifact_paths"]
    assert payload["next_action"] == "review_report"


def test_coze_confirm_false_skips_run() -> None:
    client = TestClient(app)
    project_id = create_inspected_project(client)
    prepare(client, project_id)

    response = client.post(
        f"/coze/projects/{project_id}/confirm-and-run",
        json={"confirmed": False, "run_mode": "mock", "analysis_plan_overrides": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_status"] == "skipped"
    assert payload["next_action"] == "confirm_plan"
    assert payload["artifact_manifest"] is None

