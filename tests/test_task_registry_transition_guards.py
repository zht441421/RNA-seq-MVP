import pytest

from backend.app.models.task import TaskCreateRequest, TaskStatus
from backend.app.services.task_registry import (
    create_task,
    get_task,
    reset_registry,
    update_task_status,
)


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


_LEGAL_SEQUENCE = [
    TaskStatus.PLANNED,
    TaskStatus.QC_PLACEHOLDER_READY,
    TaskStatus.RUN_PLACEHOLDER_READY,
    TaskStatus.REPORT_PLACEHOLDER_READY,
    TaskStatus.ARTIFACTS_PLACEHOLDER_READY,
    TaskStatus.AUDIT_PLACEHOLDER_READY,
]


def _create_registry_task():
    return create_task(
        TaskCreateRequest(
            task_type="bulk_rnaseq_placeholder",
            parameters={
                "project_name": "demo_bulk_rnaseq",
                "omics_type": "bulk_rnaseq",
                "cohort": "stable_metadata",
            },
        )
    )


def _transition(task_id: str, status: TaskStatus):
    return update_task_status(
        task_id=task_id,
        status=status,
        event_type=f"{status.value}_event",
        message=f"Transitioned to {status.value}.",
        metadata={"next_status": status.value},
    )


def _advance_to(task_id: str, target_status: TaskStatus) -> None:
    for status in _LEGAL_SEQUENCE:
        task = _transition(task_id, status)
        assert task is not None
        if status == target_status:
            return
    raise AssertionError(f"Target status was not reached: {target_status.value}")


def test_registry_accepts_only_the_full_placeholder_lifecycle_order() -> None:
    task = _create_registry_task()
    task_id = task.task_id
    original_parameters = dict(task.parameters)

    for index, status in enumerate(_LEGAL_SEQUENCE, start=1):
        updated = _transition(task_id, status)

        assert updated is not None
        stored = get_task(task_id)
        assert stored is updated
        assert stored.task_id == task_id
        assert stored.status == status
        assert stored.parameters == original_parameters
        assert stored.updated_at == f"2026-01-01T00:00:0{index}Z"
        assert len(stored.lifecycle_events) == index + 1
        assert stored.lifecycle_events[-1].metadata == {"next_status": status.value}


@pytest.mark.parametrize(
    ("starting_status", "rejected_status", "expected_message"),
    [
        (
            TaskStatus.CREATED,
            TaskStatus.RUN_PLACEHOLDER_READY,
            "Invalid task status transition: created -> run_placeholder_ready",
        ),
        (
            TaskStatus.PLANNED,
            TaskStatus.ARTIFACTS_PLACEHOLDER_READY,
            "Invalid task status transition: planned -> artifacts_placeholder_ready",
        ),
        (
            TaskStatus.RUN_PLACEHOLDER_READY,
            TaskStatus.PLANNED,
            "Invalid task status transition: run_placeholder_ready -> planned",
        ),
        (
            TaskStatus.AUDIT_PLACEHOLDER_READY,
            TaskStatus.PLANNED,
            "Invalid task status transition: audit_placeholder_ready -> planned",
        ),
    ],
)
def test_registry_rejects_skips_rollbacks_and_terminal_transitions_without_mutation(
    starting_status: TaskStatus,
    rejected_status: TaskStatus,
    expected_message: str,
) -> None:
    task = _create_registry_task()
    if starting_status != TaskStatus.CREATED:
        _advance_to(task.task_id, starting_status)

    stored = get_task(task.task_id)
    assert stored is not None
    original_status = stored.status
    original_event_count = len(stored.lifecycle_events)
    original_updated_at = stored.updated_at

    with pytest.raises(ValueError, match=expected_message):
        _transition(task.task_id, rejected_status)

    unchanged = get_task(task.task_id)
    assert unchanged is not None
    assert unchanged.status == original_status
    assert len(unchanged.lifecycle_events) == original_event_count
    assert unchanged.updated_at == original_updated_at


def test_unknown_task_status_transition_returns_none() -> None:
    result = update_task_status(
        task_id="task_missing",
        status=TaskStatus.PLANNED,
        event_type="plan_generated",
        message="Placeholder analysis plan generated and task status updated.",
    )

    assert result is None


def test_invalid_status_value_has_stable_error() -> None:
    task = _create_registry_task()

    with pytest.raises(ValueError, match="Invalid task status: not_a_real_status"):
        update_task_status(
            task_id=task.task_id,
            status="not_a_real_status",
            event_type="invalid",
            message="Invalid transition.",
        )
