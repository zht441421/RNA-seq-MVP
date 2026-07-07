from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    QC_PLACEHOLDER_READY = "qc_placeholder_ready"
    RUN_PLACEHOLDER_READY = "run_placeholder_ready"
    REPORT_PLACEHOLDER_READY = "report_placeholder_ready"
    ARTIFACTS_PLACEHOLDER_READY = "artifacts_placeholder_ready"
    AUDIT_PLACEHOLDER_READY = "audit_placeholder_ready"


class TaskCreateRequest(BaseModel):
    task_type: str = "placeholder"
    parameters: Dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


class TaskLifecycleEvent(BaseModel):
    event_type: str
    message: str
    actor: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskRecord(TaskResponse):
    task_type: str
    project_name: str
    omics_type: str
    created_at: str
    updated_at: str
    lifecycle_events: List[TaskLifecycleEvent] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AnalysisPlanRequest(BaseModel):
    task_id: Optional[str] = None
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
    task_id: Optional[str] = None
    project_name: str
    omics_type: str
    input_level: str
    status: str = "planned"
    recommended_workflow: List[AnalysisStep]
    reliability_notes: List[str] = Field(default_factory=list)


class QCRequest(BaseModel):
    task_id: Optional[str] = None
    project_name: str
    omics_type: str
    input_level: str
    metadata_file: str
    count_matrix_file: str
    sample_id_column: str
    group_column: str
    contrast: str


class QCCheck(BaseModel):
    check_id: str
    name: str
    description: str
    status: str = "planned"
    required: bool = True


class QCResponse(BaseModel):
    task_id: Optional[str] = None
    project_name: str
    omics_type: str
    input_level: str
    status: str = "qc_planned"
    qc_checks: List[QCCheck]
    reliability_gates: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class TaskRunRequest(BaseModel):
    task_id: str
    project_name: str
    omics_type: str
    input_level: str
    analysis_goal: List[str] = Field(default_factory=list)
    group_column: Optional[str] = None
    contrast: Optional[str] = None


class TaskRunStep(BaseModel):
    step_id: str
    name: str
    status: str
    message: str


class TaskRunResponse(BaseModel):
    task_id: str
    project_name: str
    status: str = "run_placeholder_completed"
    run_steps: List[TaskRunStep]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    section_id: str
    title: str
    content: str


class TaskReportResponse(BaseModel):
    task_id: str
    status: str = "report_placeholder_ready"
    summary: str
    sections: List[ReportSection]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class TaskArtifact(BaseModel):
    artifact_id: str
    name: str
    artifact_type: str
    path: Optional[str] = None
    description: str
    available: bool = False


class TaskArtifactsResponse(BaseModel):
    task_id: str
    status: str = "artifacts_placeholder_ready"
    artifacts: List[TaskArtifact]
    limitations: List[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    event_id: str
    event_type: str
    message: str
    timestamp: str
    actor: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskAuditResponse(BaseModel):
    task_id: str
    status: str = "audit_placeholder_ready"
    events: List[AuditEvent]
    limitations: List[str] = Field(default_factory=list)
