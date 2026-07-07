from fastapi.testclient import TestClient

from backend.app.main import app


def test_task_qc_returns_placeholder_qc_plan() -> None:
    payload = {
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "metadata_file": "metadata.csv",
        "count_matrix_file": "counts.csv",
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }

    response = TestClient(app).post("/task/qc", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "qc_planned"
    assert body["qc_checks"]
    assert body["reliability_gates"]
    assert body["limitations"]
