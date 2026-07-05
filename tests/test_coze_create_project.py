from fastapi.testclient import TestClient

from backend.app.main import app


def test_coze_create_project() -> None:
    response = TestClient(app).post(
        "/coze/projects",
        json={
            "project_name": "coze project test",
            "omics_type": "bulk_rnaseq",
            "input_level": "count_matrix",
            "organism": "human",
            "gene_id_type": "symbol",
            "annotation_version": "unknown",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"].startswith("proj_")
    assert payload["next_action"] == "upload_or_register_files"
    assert "Project created" in payload["human_readable_summary"]

