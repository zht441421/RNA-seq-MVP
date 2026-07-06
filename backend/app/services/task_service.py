from uuid import uuid4

from backend.app.models.task import TaskCreateRequest, TaskRecord, TaskStatus


_TASKS: dict[str, TaskRecord] = {}


def create_task(request: TaskCreateRequest) -> TaskRecord:
    task_id = f"task_{uuid4().hex}"
    task = TaskRecord(
        task_id=task_id,
        status=TaskStatus.CREATED,
        message="Task created. Real RNA-seq analysis is not implemented in this Phase 2 skeleton.",
        task_type=request.task_type,
        parameters=request.parameters,
    )
    _TASKS[task_id] = task
    return task


def get_task(task_id: str) -> TaskRecord | None:
    return _TASKS.get(task_id)
