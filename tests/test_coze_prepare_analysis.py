from fastapi.testclient import TestClient

from backend.app.main import app


def create_inspected_project(client: TestClient) -> str:
    project = client.post("/coze/projects", json={"project_name": "coze prepare test"}).json()
    project_id = project["project_id"]
    client.post(
        f"/coze/projects/{project_id}/inspect",
        json={
            "count_matrix_path": "examples/real_small_count_matrix.csv",
            "metadata_path": "examples/real_small_metadata.csv",
        },
    ).raise_for_status()
    return project_id


def test_coze_prepare_analysis_runs_qc_and_plan() -> None:
    client = TestClient(app)
    project_id = create_inspected_project(client)

    response = client.post(
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
            "run_enrichment": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["qc_status"] == "pass"
    assert payload["next_action"] == "confirm_and_run"
    assert payload["recommended_plan"]["primary_method"] == "DESeq2"
    assert payload["requires_user_confirmation"] is True

