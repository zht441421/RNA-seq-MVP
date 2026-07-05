from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.project import ProjectStatus
from backend.app.models.qc_report import QCReport
from backend.app.models.reliability import ReliabilityAssessment


class OmicsType(str, Enum):
    BULK_RNASEQ = "bulk_rnaseq"


class InputLevel(str, Enum):
    COUNT_MATRIX = "count_matrix"


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    omics_type: OmicsType = OmicsType.BULK_RNASEQ


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    omics_type: str
    status: ProjectStatus


class FileRegistrationRequest(BaseModel):
    count_matrix_file: str
    metadata_file: str


class FileRegistrationResponse(BaseModel):
    project_id: str
    count_matrix_file: str
    metadata_file: str
    status: ProjectStatus


class FileInspection(BaseModel):
    file_path: str
    file_name: str
    extension: str
    sha256: str
    columns: List[str] = Field(default_factory=list)
    row_count: int
    preview: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InspectRequest(BaseModel):
    count_matrix_file: Optional[str] = None
    metadata_file: Optional[str] = None


class InspectResponse(BaseModel):
    project_id: str
    count_matrix: FileInspection
    metadata: FileInspection
    detected_schema: Dict[str, Any]


class BulkRNASeqAnalysisConfig(BaseModel):
    project_id: str
    omics_type: OmicsType = OmicsType.BULK_RNASEQ
    input_level: InputLevel = InputLevel.COUNT_MATRIX
    count_matrix_file: str
    metadata_file: str
    sample_id_column: str
    gene_id_column: str
    group_column: str
    reference_group: str
    test_group: str
    batch_column: Optional[str] = None
    covariates: List[str] = Field(default_factory=list)
    organism: Optional[str] = None
    gene_id_type: Optional[str] = None
    annotation_version: Optional[str] = None
    fdr_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    log2fc_threshold: float = Field(default=1.0, ge=0.0)
    validation_methods: List[str] = Field(default_factory=lambda: ["edgeR", "limma_voom"])


class ConfirmPlanRequest(BaseModel):
    plan_id: str
    confirmed: bool


class RunRequest(BaseModel):
    plan_id: Optional[str] = None


class StatusResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    details: Dict[str, Any] = Field(default_factory=dict)


class RunResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    plan: AnalysisPlan
    reliability: ReliabilityAssessment
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    result_summary: Dict[str, Any] = Field(default_factory=dict)


class ResultsResponse(BaseModel):
    project_id: str
    status: ProjectStatus
    reliability: Optional[ReliabilityAssessment] = None
    result_summary: Dict[str, Any] = Field(default_factory=dict)
    reliability_grade: Optional[str] = None
    strong_conclusion_allowed: bool = False
    primary_method_status: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    validation_consistency_score: Optional[float] = None
    artifact_presence_summary: Dict[str, str] = Field(default_factory=dict)
    interpretation_summary: Dict[str, Any] = Field(default_factory=dict)
    top_genes: List[Dict[str, Any]] = Field(default_factory=list)
    interpretation_guardrails: List[str] = Field(default_factory=list)


class ArtifactsResponse(BaseModel):
    project_id: str
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
