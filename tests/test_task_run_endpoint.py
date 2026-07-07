from fastapi.testclient import TestClient

from backend.app.main import app


def test_task_run_returns_placeholder_run_result() -> None:
    payload = {
        "task_id": "task_demo",
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }

    response = TestClient(app).post("/task/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "run_placeholder_completed"
    assert body["run_steps"]
    assert "artifacts" in body
    assert body["limitations"]
