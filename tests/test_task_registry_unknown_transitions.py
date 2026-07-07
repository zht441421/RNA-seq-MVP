import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def _plan_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _qc_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "metadata_file": "metadata.csv",
        "count_matrix_file": "counts.csv",
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/task/plan", _plan_payload("task_missing")),
        ("/task/qc", _qc_payload("task_missing")),
        ("/task/run", _plan_payload("task_missing")),
    ],
)
def test_unknown_task_id_transitions_return_deterministic_404(
    path: str,
    payload: dict[str, object],
) -> None:
    response = TestClient(app).post(path, json=payload)

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found: task_missing"}
