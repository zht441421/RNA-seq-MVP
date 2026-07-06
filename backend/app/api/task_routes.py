from fastapi import APIRouter, HTTPException

from backend.app.models.task import TaskCreateRequest, TaskResponse
from backend.app.services.task_service import create_task, get_task


router = APIRouter(prefix="/task", tags=["task"])


@router.post("/create", response_model=TaskResponse)
def create_task_endpoint(request: TaskCreateRequest | None = None) -> TaskResponse:
    task = create_task(request or TaskCreateRequest())
    return TaskResponse(task_id=task.task_id, status=task.status, message=task.message)


@router.get("/{task_id}/status", response_model=TaskResponse)
def get_task_status(task_id: str) -> TaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return TaskResponse(task_id=task.task_id, status=task.status, message=task.message)
