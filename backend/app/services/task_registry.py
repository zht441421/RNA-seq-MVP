from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.models.task import (
    TaskCreateRequest,
    TaskLifecycleEvent,
    TaskRecord,
    TaskStatus,
)
from backend.app.services.task_store import get_task_store
from backend.app.services.execution_trace import begin_execution_trace
from backend.app.services.execution_trace import complete_execution_trace
from backend.app.services.execution_trace import reset_execution_traces


_TASKS: dict[str, TaskRecord] = {}
_NEXT_TASK_NUMBER = 1
_BASE_TIMESTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)
_ALLOWED_STATUS_TRANSITIONS: dict[TaskStatus, TaskStatus] = {
    TaskStatus.CREATED: TaskStatus.PLANNED,
    TaskStatus.PLANNED: TaskStatus.QC_PLACEHOLDER_READY,
    TaskStatus.QC_PLACEHOLDER_READY: TaskStatus.RUN_PLACEHOLDER_READY,
    TaskStatus.RUN_PLACEHOLDER_READY: TaskStatus.REPORT_PLACEHOLDER_READY,
    TaskStatus.REPORT_PLACEHOLDER_READY: TaskStatus.ARTIFACTS_PLACEHOLDER_READY,
    TaskStatus.ARTIFACTS_PLACEHOLDER_READY: TaskStatus.AUDIT_PLACEHOLDER_READY,
}


def _next_task_id() -> str:
    return f"task_{_NEXT_TASK_NUMBER:04d}"


def _timestamp_for_task(task_number: int) -> str:
    timestamp = _BASE_TIMESTAMP + timedelta(seconds=task_number - 1)
    return timestamp.isoformat().replace("+00:00", "Z")


def _timestamp_for_task_event(task: TaskRecord) -> str:
    created_at = datetime.fromisoformat(task.created_at.replace("Z", "+00:00"))
    timestamp = created_at + timedelta(seconds=max(len(task.lifecycle_events) - 1, 0))
    return timestamp.isoformat().replace("+00:00", "Z")


def _string_parameter(parameters: dict[str, Any], key: str, default: str) -> str:
    value = parameters.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return default


def create_task(request: TaskCreateRequest | None = None) -> TaskRecord:
    global _NEXT_TASK_NUMBER

    request = request or TaskCreateRequest()
    _sync_next_task_number_from_store()
    task_number = _NEXT_TASK_NUMBER
    task_id = _next_task_id()
    timestamp = _timestamp_for_task(task_number)
    creation_trace = complete_execution_trace(
        begin_execution_trace(
            task_id,
            "task_created",
            {
                "task_type": request.task_type,
                "omics_type": request.parameters.get("omics_type", "unspecified"),
            },
        )
    )

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
    _persist_task(task)
    _NEXT_TASK_NUMBER += 1
    return task


def get_task(task_id: str) -> TaskRecord | None:
    task = _TASKS.get(task_id)
    if task is not None:
        return task
    try:
        persisted_task = get_task_store().load_task(task_id)
    except ValueError:
        return None
    if persisted_task is not None:
        _TASKS[task_id] = persisted_task
        _sync_next_task_number_from_store()
    return persisted_task


def _coerce_task_status(status: TaskStatus | str) -> TaskStatus:
    try:
        return TaskStatus(status)
    except ValueError as exc:
        raise ValueError(f"Invalid task status: {status}") from exc


def _validate_status_transition(current_status: TaskStatus, next_status: TaskStatus) -> None:
    if _ALLOWED_STATUS_TRANSITIONS.get(current_status) != next_status:
        raise ValueError(
            f"Invalid task status transition: {current_status.value} -> {next_status.value}"
        )


def append_lifecycle_event(
    task_id: str,
    event_type: str,
    message: str,
    actor: str = "system",
    metadata: dict[str, Any] | None = None,
) -> TaskRecord | None:
    task = get_task(task_id)
    if task is None:
        return None

    task.lifecycle_events.append(
        TaskLifecycleEvent(
            event_type=event_type,
            message=message,
            actor=actor,
            metadata=metadata or {},
        )
    )
    task.updated_at = _timestamp_for_task_event(task)
    _persist_task(task)
    return task


def update_task_status(
    task_id: str,
    status: TaskStatus | str,
    event_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> TaskRecord | None:
    task = get_task(task_id)
    if task is None:
        return None

    next_status = _coerce_task_status(status)
    _validate_status_transition(task.status, next_status)

    task.status = next_status
    task.message = message
    return append_lifecycle_event(
        task_id=task_id,
        event_type=event_type,
        message=message,
        actor="system",
        metadata=metadata,
    )


def list_tasks() -> list[TaskRecord]:
    return list(_TASKS.values())


def save_task_artifacts(task_id: str, artifacts: list[dict[str, Any]]) -> None:
    get_task_store().replace_task_artifacts(task_id, artifacts)


def list_task_artifacts(task_id: str) -> list[dict[str, Any]]:
    return get_task_store().list_artifact_metadata(task_id)


def save_task_input(
    task_id: str,
    *,
    input_role: str,
    safe_relative_path: str,
    original_filename: str | None = None,
    content_type: str | None = None,
    file_size_bytes: int | None = None,
    checksum_sha256: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    get_task_store().save_task_input_metadata(
        task_id=task_id,
        input_role=input_role,
        safe_relative_path=safe_relative_path,
        original_filename=original_filename,
        content_type=content_type,
        file_size_bytes=file_size_bytes,
        checksum_sha256=checksum_sha256,
        metadata=metadata,
    )


def list_task_inputs(task_id: str) -> list[dict[str, Any]]:
    return get_task_store().list_task_input_metadata(task_id)


def reset_in_memory_registry() -> None:
    global _NEXT_TASK_NUMBER

    _TASKS.clear()
    try:
        _NEXT_TASK_NUMBER = get_task_store().next_task_number()
    except ValueError:
        _NEXT_TASK_NUMBER = 1


def reset_registry(*, clear_store: bool = True) -> None:
    global _NEXT_TASK_NUMBER

    _TASKS.clear()
    if clear_store:
        get_task_store().clear()
    reset_execution_traces()
    _NEXT_TASK_NUMBER = 1


def _persist_task(task: TaskRecord) -> None:
    get_task_store().save_task(task)


def _sync_next_task_number_from_store() -> None:
    global _NEXT_TASK_NUMBER

    next_task_number = get_task_store().next_task_number()
    if next_task_number > _NEXT_TASK_NUMBER:
        _NEXT_TASK_NUMBER = next_task_number
