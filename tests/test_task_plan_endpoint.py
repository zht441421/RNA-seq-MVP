from fastapi.testclient import TestClient

from backend.app.main import app


def test_task_plan_returns_placeholder_analysis_plan() -> None:
    payload = {
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }

    response = TestClient(app).post("/task/plan", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["project_name"] == "demo_bulk_rnaseq"
    assert body["omics_type"] == "bulk_rnaseq"
    assert body["input_level"] == "count_matrix"
    assert body["status"] == "planned"
    assert body["recommended_workflow"]
    assert body["reliability_notes"]
