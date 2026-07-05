from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QCSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class QCStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    INFO = "info"


class QCCheck(BaseModel):
    name: str
    status: QCStatus
    severity: QCSeverity
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    severity: QCSeverity
    code: str
    message: str
    suggestion: str
    details: Dict[str, Any] = Field(default_factory=dict)


class SampleAlignment(BaseModel):
    metadata_sample_count: int
    matrix_sample_count: int
    matched_sample_count: int
    missing_in_metadata: List[str] = Field(default_factory=list)
    missing_in_count_matrix: List[str] = Field(default_factory=list)
    ordered_match: bool = False


class LibrarySizeSummary(BaseModel):
    sample_count: int
    minimum: float
    maximum: float
    mean: float
    median: float
    total_by_sample: Dict[str, float] = Field(default_factory=dict)


class LowCountGeneSummary(BaseModel):
    total_genes: int
    low_count_genes: int
    low_count_fraction: float
    min_total_count: int


class BatchGroupAssessment(BaseModel):
    batch_column: str
    is_potentially_confounding: bool
    table: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    message: str


class QCReport(BaseModel):
    project_id: str
    passed: bool
    checks: List[QCCheck] = Field(default_factory=list)
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    group_counts: Dict[str, int] = Field(default_factory=dict)
    sample_alignment: Optional[SampleAlignment] = None
    library_size_summary: Optional[LibrarySizeSummary] = None
    low_count_gene_summary: Optional[LowCountGeneSummary] = None
    batch_group_assessment: Optional[BatchGroupAssessment] = None
