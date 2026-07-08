from pathlib import Path

import pytest

from backend.app.models.task import TaskCreateRequest, TaskStatus
from backend.app.services.task_registry import (
    create_task,
    get_task,
    reset_in_memory_registry,
    reset_registry,
    update_task_status,
)


def test_registry_reloads_status_and_events_from_persistent_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "tasks.sqlite3"))
    reset_registry()
    created = create_task(
        TaskCreateRequest(
            task_type="bulk_rnaseq_placeholder",
            parameters={"project_name": "demo_bulk_rnaseq"},
        )
    )
    assert update_task_status(
        task_id=created.task_id,
        status=TaskStatus.PLANNED,
        event_type="plan_generated",
        message="Placeholder analysis plan generated and task status updated.",
    )
    assert update_task_status(
        task_id=created.task_id,
        status=TaskStatus.QC_PLACEHOLDER_READY,
        event_type="qc_checked",
        message="Placeholder QC checks generated and task status updated.",
    )

    reset_in_memory_registry()
    restored = get_task(created.task_id)

    assert restored is not None
    assert restored.status == TaskStatus.QC_PLACEHOLDER_READY
    assert [event.event_type for event in restored.lifecycle_events] == [
        "task_created",
        "plan_generated",
        "qc_checked",
    ]
    reset_registry()
