from enum import Enum
from typing import Any, Dict, List, Optional

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


class AnalysisPlanRequest(BaseModel):
    project_name: str
    omics_type: str
    input_level: str
    analysis_goal: List[str] = Field(default_factory=list)
    group_column: Optional[str] = None
    contrast: Optional[str] = None


class AnalysisStep(BaseModel):
    order: int
    name: str
    description: str
    status: str = "planned"


class AnalysisPlanResponse(BaseModel):
    project_name: str
    omics_type: str
    input_level: str
    status: str = "planned"
    recommended_workflow: List[AnalysisStep]
    reliability_notes: List[str] = Field(default_factory=list)
