from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class ReliabilityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class ReliabilityAssessment(BaseModel):
    project_id: str
    grade: ReliabilityGrade
    strong_conclusion_allowed: bool
    rationale: List[str] = Field(default_factory=list)
    stop_conditions: List[str] = Field(default_factory=list)
    downgrade_conditions: List[str] = Field(default_factory=list)
    audit_notes: List[str] = Field(default_factory=list)

