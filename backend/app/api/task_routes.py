from fastapi import APIRouter, HTTPException

from backend.app.models.task import (
    AnalysisPlanRequest,
    AnalysisPlanResponse,
    AnalysisStep,
    AuditEvent,
    QCCheck,
    QCRequest,
    QCResponse,
    ReportSection,
    TaskArtifact,
    TaskArtifactsResponse,
    TaskAuditResponse,
    TaskCreateRequest,
    TaskReportResponse,
    TaskResponse,
    TaskRunRequest,
    TaskRunResponse,
    TaskRunStep,
)
from backend.app.services.task_service import create_task, get_task


router = APIRouter(prefix="/task", tags=["task"])


@router.post("/create", response_model=TaskResponse)
def create_task_endpoint(request: TaskCreateRequest | None = None) -> TaskResponse:
    task = create_task(request or TaskCreateRequest())
    return TaskResponse(task_id=task.task_id, status=task.status, message=task.message)


@router.post("/plan", response_model=AnalysisPlanResponse, response_model_exclude_none=True)
def create_analysis_plan(request: AnalysisPlanRequest) -> AnalysisPlanResponse:
    group_column = request.group_column or "not specified"
    contrast = request.contrast or "not specified"
    analysis_goals = ", ".join(request.analysis_goal) if request.analysis_goal else "not specified"

    return AnalysisPlanResponse(
        task_id=request.task_id,
        project_name=request.project_name,
        omics_type=request.omics_type,
        input_level=request.input_level,
        status="planned",
        recommended_workflow=[
            AnalysisStep(
                order=1,
                name="Input review",
                description=(
                    f"Confirm project '{request.project_name}' uses {request.omics_type} "
                    f"data at the {request.input_level} level."
                ),
            ),
            AnalysisStep(
                order=2,
                name="Goal alignment",
                description=f"Map requested analysis goals to a placeholder workflow: {analysis_goals}.",
            ),
            AnalysisStep(
                order=3,
                name="Metadata check",
                description=f"Plan validation for group column '{group_column}' and contrast '{contrast}'.",
            ),
            AnalysisStep(
                order=4,
                name="Bulk RNA-seq method planning",
                description=(
                    "Reserve differential expression method selection for a later execution phase; "
                    "no DESeq2, edgeR, limma, or RNA-seq computation is run here."
                ),
            ),
            AnalysisStep(
                order=5,
                name="Reporting outline",
                description=(
                    "Plan placeholder outputs for QC notes, differential expression readiness, "
                    "reliability notes, and future artifacts."
                ),
            ),
        ],
        reliability_notes=[
            "This is a deterministic placeholder plan for API integration only.",
            "No real DESeq2, edgeR, limma, or RNA-seq execution is performed by this endpoint.",
            "Future execution should validate files, metadata, design formula, and runtime environment before analysis.",
        ],
    )


@router.post("/qc", response_model=QCResponse, response_model_exclude_none=True)
def create_qc_plan(request: QCRequest) -> QCResponse:
    return QCResponse(
        task_id=request.task_id,
        project_name=request.project_name,
        omics_type=request.omics_type,
        input_level=request.input_level,
        status="qc_planned",
        qc_checks=[
            QCCheck(
                check_id="qc_1",
                name="File availability check",
                description="Confirm metadata and count matrix files are provided.",
            ),
            QCCheck(
                check_id="qc_2",
                name="Sample ID matching check",
                description="Plan validation that sample IDs in metadata match count matrix columns.",
            ),
            QCCheck(
                check_id="qc_3",
                name="Group column check",
                description="Plan validation that the group column exists and supports the requested contrast.",
            ),
            QCCheck(
                check_id="qc_4",
                name="Count matrix structure check",
                description=(
                    "Plan validation for gene-by-sample count matrix structure "
                    "and numeric count values."
                ),
            ),
        ],
        reliability_gates=[
            "metadata_file_provided",
            "count_matrix_file_provided",
            "sample_id_column_defined",
            "group_column_defined",
            "contrast_defined",
        ],
        limitations=[
            "This endpoint currently returns a QC planning skeleton only.",
            "No real file reading or count matrix validation is performed yet.",
            "Actual QC execution will be implemented in a later phase.",
        ],
    )


@router.post("/run", response_model=TaskRunResponse)
def run_task_placeholder(request: TaskRunRequest) -> TaskRunResponse:
    return TaskRunResponse(
        task_id=request.task_id,
        project_name=request.project_name,
        status="run_placeholder_completed",
        run_steps=[
            TaskRunStep(
                step_id="run_1",
                name="Load task configuration",
                status="completed",
                message="Task configuration received.",
            ),
            TaskRunStep(
                step_id="run_2",
                name="QC execution placeholder",
                status="completed",
                message="QC execution is not implemented yet.",
            ),
            TaskRunStep(
                step_id="run_3",
                name="Differential expression placeholder",
                status="completed",
                message="DESeq2, edgeR, and limma execution are not implemented yet.",
            ),
        ],
        artifacts=[],
        limitations=[
            "This endpoint does not run real RNA-seq analysis.",
            "No files are read or written.",
            "No statistical or biological conclusion should be drawn from this placeholder response.",
        ],
    )


@router.get("/{task_id}/report", response_model=TaskReportResponse)
def get_task_report(task_id: str) -> TaskReportResponse:
    return TaskReportResponse(
        task_id=task_id,
        status="report_placeholder_ready",
        summary="Placeholder report generated for API integration. No real RNA-seq analysis was performed.",
        sections=[
            ReportSection(
                section_id="report_1",
                title="Task Overview",
                content="This placeholder report summarizes the submitted task configuration.",
            ),
            ReportSection(
                section_id="report_2",
                title="QC Summary",
                content=(
                    "QC execution is not implemented yet. "
                    "This section is reserved for future QC results."
                ),
            ),
            ReportSection(
                section_id="report_3",
                title="Analysis Summary",
                content=(
                    "Differential expression execution is not implemented yet. "
                    "This section is reserved for future RNA-seq results."
                ),
            ),
            ReportSection(
                section_id="report_4",
                title="Reliability Notes",
                content=(
                    "No biological or statistical conclusion should be drawn "
                    "from this placeholder report."
                ),
            ),
        ],
        artifacts=[],
        limitations=[
            "This endpoint does not generate a real report file.",
            "No input files are read.",
            "No QC, DESeq2, edgeR, limma, or enrichment analysis is executed.",
            "No biological conclusion should be drawn from this response.",
        ],
    )


@router.get("/{task_id}/artifacts", response_model=TaskArtifactsResponse)
def get_task_artifacts(task_id: str) -> TaskArtifactsResponse:
    return TaskArtifactsResponse(
        task_id=task_id,
        status="artifacts_placeholder_ready",
        artifacts=[
            TaskArtifact(
                artifact_id="artifact_1",
                name="qc_report_placeholder.md",
                artifact_type="qc_report",
                path=None,
                description="Placeholder QC report artifact. No file is generated yet.",
                available=False,
            ),
            TaskArtifact(
                artifact_id="artifact_2",
                name="analysis_report_placeholder.md",
                artifact_type="analysis_report",
                path=None,
                description="Placeholder analysis report artifact. No file is generated yet.",
                available=False,
            ),
            TaskArtifact(
                artifact_id="artifact_3",
                name="audit_log_placeholder.json",
                artifact_type="audit_log",
                path=None,
                description="Placeholder audit log artifact. No file is generated yet.",
                available=False,
            ),
        ],
        limitations=[
            "This endpoint does not read or write real artifact files.",
            "Artifact paths are placeholders and are not downloadable yet.",
            "Real artifact generation will be implemented in a later phase.",
        ],
    )


@router.get("/{task_id}/audit", response_model=TaskAuditResponse)
def get_task_audit(task_id: str) -> TaskAuditResponse:
    return TaskAuditResponse(
        task_id=task_id,
        status="audit_placeholder_ready",
        events=[
            AuditEvent(
                event_id="audit_1",
                event_type="task_created",
                message="Placeholder task creation event.",
                timestamp="placeholder_timestamp",
                actor="system",
                metadata={},
            ),
            AuditEvent(
                event_id="audit_2",
                event_type="plan_generated",
                message="Placeholder analysis plan generation event.",
                timestamp="placeholder_timestamp",
                actor="system",
                metadata={},
            ),
            AuditEvent(
                event_id="audit_3",
                event_type="qc_checked",
                message="Placeholder QC checking event.",
                timestamp="placeholder_timestamp",
                actor="system",
                metadata={},
            ),
            AuditEvent(
                event_id="audit_4",
                event_type="run_placeholder_executed",
                message=(
                    "Placeholder task run event. "
                    "No real RNA-seq analysis was performed."
                ),
                timestamp="placeholder_timestamp",
                actor="system",
                metadata={},
            ),
            AuditEvent(
                event_id="audit_5",
                event_type="report_placeholder_generated",
                message=(
                    "Placeholder report generation event. "
                    "No real report file was created."
                ),
                timestamp="placeholder_timestamp",
                actor="system",
                metadata={},
            ),
            AuditEvent(
                event_id="audit_6",
                event_type="artifacts_placeholder_listed",
                message=(
                    "Placeholder artifact listing event. "
                    "No real files were generated."
                ),
                timestamp="placeholder_timestamp",
                actor="system",
                metadata={},
            ),
        ],
        limitations=[
            "This endpoint does not read persisted task history.",
            "Audit events are deterministic placeholders.",
            "No database or durable audit storage is implemented yet.",
            "Timestamps are placeholders and should not be treated as real execution times.",
        ],
    )


@router.get("/{task_id}/status", response_model=TaskResponse)
def get_task_status(task_id: str) -> TaskResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return TaskResponse(task_id=task.task_id, status=task.status, message=task.message)
