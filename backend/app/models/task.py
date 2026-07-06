from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    CREATED = "created"


class TaskCreateRequest(BaseModel):
    task_type: str = "placeholder"
    parameters: Dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


class TaskRecord(TaskResponse):
    task_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
