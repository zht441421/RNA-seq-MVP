from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStatus(str, Enum):
    CREATED = "created"
    FILES_UPLOADED = "files_uploaded"
    INSPECTED = "inspected"
    QC_COMPLETED = "qc_completed"
    PLAN_PROPOSED = "plan_proposed"
    PLAN_CONFIRMED = "plan_confirmed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Project(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    omics_type: str = "bulk_rnaseq"
    status: ProjectStatus = ProjectStatus.CREATED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

