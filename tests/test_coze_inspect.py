from fastapi.testclient import TestClient

from backend.app.main import app


def test_coze_inspect_detects_schema_candidates() -> None:
    client = TestClient(app)
    project = client.post(
        "/coze/projects",
        json={"project_name": "coze inspect test"},
    ).json()
    response = client.post(
        f"/coze/projects/{project['project_id']}/inspect",
        json={
            "count_matrix_path": "examples/real_small_count_matrix.csv",
            "metadata_path": "examples/real_small_metadata.csv",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "gene_id" in payload["gene_id_column_candidates"]
    assert payload["possible_sample_id_column"] == "sample_id"
    assert payload["possible_group_column"] == "condition"
    assert payload["sample_columns"] == ["C1", "C2", "C3", "T1", "T2", "T3"]
    assert payload["next_action"] == "confirm_schema_mapping"

