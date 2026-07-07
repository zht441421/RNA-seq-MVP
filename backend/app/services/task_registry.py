from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.models.task import (
    TaskCreateRequest,
    TaskLifecycleEvent,
    TaskRecord,
    TaskStatus,
)


_TASKS: dict[str, TaskRecord] = {}
_NEXT_TASK_NUMBER = 1
_BASE_TIMESTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _next_task_id() -> str:
    return f"task_{_NEXT_TASK_NUMBER:04d}"


def _timestamp_for_task(task_number: int) -> str:
    timestamp = _BASE_TIMESTAMP + timedelta(seconds=task_number - 1)
    return timestamp.isoformat().replace("+00:00", "Z")


def _string_parameter(parameters: dict[str, Any], key: str, default: str) -> str:
    value = parameters.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return default


def create_task(request: TaskCreateRequest | None = None) -> TaskRecord:
    global _NEXT_TASK_NUMBER

    request = request or TaskCreateRequest()
    task_number = _NEXT_TASK_NUMBER
    task_id = _next_task_id()
    timestamp = _timestamp_for_task(task_number)

    task = TaskRecord(
        task_id=task_id,
        status=TaskStatus.CREATED,
        message="Task created. Real RNA-seq analysis is not implemented in this Phase 2 skeleton.",
        task_type=request.task_type,
        project_name=_string_parameter(request.parameters, "project_name", "unspecified"),
        omics_type=_string_parameter(request.parameters, "omics_type", "unspecified"),
        created_at=timestamp,
        updated_at=timestamp,
        lifecycle_events=[
            TaskLifecycleEvent(
                event_type="task_created",
                message="Task record created in in-memory registry.",
                actor="system",
            )
        ],
        parameters=request.parameters,
    )

    _TASKS[task_id] = task
    _NEXT_TASK_NUMBER += 1
    return task


def get_task(task_id: str) -> TaskRecord | None:
    return _TASKS.get(task_id)


def list_tasks() -> list[TaskRecord]:
    return list(_TASKS.values())


def reset_registry() -> None:
    global _NEXT_TASK_NUMBER

    _TASKS.clear()
    _NEXT_TASK_NUMBER = 1
