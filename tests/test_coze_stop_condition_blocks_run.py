from fastapi.testclient import TestClient

from backend.app.main import app


def test_coze_prepare_analysis_stop_condition_returns_fix_input() -> None:
    client = TestClient(app)
    project = client.post("/coze/projects", json={"project_name": "coze stop test"}).json()
    project_id = project["project_id"]
    client.post(
        f"/coze/projects/{project_id}/inspect",
        json={
            "count_matrix_path": "examples/real_small_count_matrix.csv",
            "metadata_path": "examples/real_small_metadata.csv",
        },
    ).raise_for_status()

    response = client.post(
        f"/coze/projects/{project_id}/prepare-analysis",
        json={
            "gene_id_column": "gene_id",
            "sample_id_column": "missing_sample_column",
            "group_column": "condition",
            "reference_group": "control",
            "test_group": "treatment",
            "batch_column": None,
            "covariates": [],
            "fdr_threshold": 0.05,
            "log2fc_threshold": 1.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["qc_status"] == "fail"
    assert payload["next_action"] == "fix_input"
    assert payload["recommended_plan"] is None
    assert payload["stop_conditions"]


def test_coze_stop_condition_blocks_confirm_and_run() -> None:
    client = TestClient(app)
    project = client.post("/coze/projects", json={"project_name": "coze blocked run test"}).json()
    project_id = project["project_id"]
    client.post(
        f"/coze/projects/{project_id}/inspect",
        json={
            "count_matrix_path": "examples/real_small_count_matrix.csv",
            "metadata_path": "examples/real_small_metadata.csv",
        },
    ).raise_for_status()
    client.post(
        f"/coze/projects/{project_id}/prepare-analysis",
        json={
            "gene_id_column": "gene_id",
            "sample_id_column": "missing_sample_column",
            "group_column": "condition",
            "reference_group": "control",
            "test_group": "treatment",
            "batch_column": None,
            "covariates": [],
        },
    ).raise_for_status()

    response = client.post(
        f"/coze/projects/{project_id}/confirm-and-run",
        json={"confirmed": True, "run_mode": "mock", "analysis_plan_overrides": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_status"] == "skipped"
    assert payload["next_action"] == "fix_input"
    assert payload["reliability_grade"] == "E"
    assert payload["stop_conditions"]

