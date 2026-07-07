import pytest

from backend.app.models.task import TaskCreateRequest, TaskStatus
from backend.app.services.task_registry import create_task, get_task, reset_registry


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def test_create_task_returns_deterministic_task_ids() -> None:
    first_task = create_task(TaskCreateRequest())
    second_task = create_task(TaskCreateRequest())

    assert first_task.task_id == "task_0001"
    assert second_task.task_id == "task_0002"


def test_get_task_returns_stored_task_record() -> None:
    created = create_task(
        TaskCreateRequest(
            task_type="bulk_rnaseq_placeholder",
            parameters={
                "project_name": "demo_bulk_rnaseq",
                "omics_type": "bulk_rnaseq",
            },
        )
    )

    stored = get_task(created.task_id)

    assert stored is not None
    assert stored.task_id == "task_0001"
    assert stored.status == TaskStatus.CREATED
    assert stored.project_name == "demo_bulk_rnaseq"
    assert stored.omics_type == "bulk_rnaseq"
    assert stored.created_at == "2026-01-01T00:00:00Z"
    assert stored.updated_at == "2026-01-01T00:00:00Z"
    assert stored.lifecycle_events[0].event_type == "task_created"
    assert stored.lifecycle_events[0].message == "Task record created in in-memory registry."
    assert stored.lifecycle_events[0].actor == "system"


def test_reset_registry_isolates_task_ids_for_tests() -> None:
    create_task(TaskCreateRequest())

    reset_registry()
    recreated = create_task(TaskCreateRequest())

    assert recreated.task_id == "task_0001"
