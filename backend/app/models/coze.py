from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CozeCreateProjectRequest(BaseModel):
    project_name: str = Field(..., min_length=1)
    omics_type: str = "bulk_rnaseq"
    input_level: str = "count_matrix"
    organism: str = "unknown"
    gene_id_type: str = "unknown"
    annotation_version: str = "unknown"


class CozeCreateProjectResponse(BaseModel):
    project_id: str
    human_readable_summary: str
    next_action: str
    warnings: List[str] = Field(default_factory=list)


class CozeInspectRequest(BaseModel):
    count_matrix_path: str
    metadata_path: str


class CozeInspectResponse(BaseModel):
    project_id: str
    gene_id_column_candidates: List[str] = Field(default_factory=list)
    sample_columns: List[str] = Field(default_factory=list)
    metadata_columns: List[str] = Field(default_factory=list)
    possible_sample_id_column: Optional[str] = None
    possible_group_column: Optional[str] = None
    possible_batch_column: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    validation_issues: List[Dict[str, Any]] = Field(default_factory=list)
    human_readable_summary: str
    next_action: str


class CozePrepareAnalysisRequest(BaseModel):
    gene_id_column: str
    sample_id_column: str
    group_column: str
    reference_group: str
    test_group: str
    batch_column: Optional[str] = None
    covariates: List[str] = Field(default_factory=list)
    fdr_threshold: float = 0.05
    log2fc_threshold: float = 1.0
    run_enrichment: bool = False


class CozePrepareAnalysisResponse(BaseModel):
    project_id: str
    qc_status: str
    stop_conditions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validation_issues: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_plan: Optional[Dict[str, Any]] = None
    requires_user_confirmation: bool = True
    human_readable_summary: str
    next_action: str


class CozeConfirmAndRunRequest(BaseModel):
    confirmed: bool
    run_mode: Optional[str] = None
    analysis_plan_overrides: Dict[str, Any] = Field(default_factory=dict)


class CozeConfirmAndRunResponse(BaseModel):
    project_id: str
    run_status: str
    reliability_grade: Optional[str] = None
    allowed_conclusion_level: str
    human_readable_summary: str
    artifact_manifest: Optional[Dict[str, Any]] = None
    artifact_paths: List[str] = Field(default_factory=list)
    next_action: str
    warnings: List[str] = Field(default_factory=list)
    stop_conditions: List[str] = Field(default_factory=list)


class CozeStatusResponse(BaseModel):
    project_id: str
    status: str
    current_stage: str
    run_status: Optional[str] = None
    reliability_grade: Optional[str] = None
    human_readable_summary: str
    next_action: str


class CozeReportResponse(BaseModel):
    project_id: str
    summary_markdown: str = ""
    qc_report_markdown: str = ""
    method_selection_markdown: str = ""
    reliability_report_markdown: str = ""
    audit_log: Dict[str, Any] = Field(default_factory=dict)
    artifact_manifest: Dict[str, Any] = Field(default_factory=dict)
    allowed_conclusion_level: str
    strong_conclusion_allowed: bool = False
    final_status: Optional[str] = None
    reliability_grade: Optional[str] = None
    primary_method_status: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    validation_consistency_score: Optional[float] = None
    artifact_presence_summary: Dict[str, str] = Field(default_factory=dict)
    interpretation_summary: Dict[str, Any] = Field(default_factory=dict)
    top_genes: List[Dict[str, Any]] = Field(default_factory=list)
    interpretation_guardrails: List[str] = Field(default_factory=list)
    export_metadata: Dict[str, Any] = Field(default_factory=dict)
