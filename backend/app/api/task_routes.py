from datetime import datetime, timedelta

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
    TaskInputFileValidationResponse,
    TaskRecord,
    TaskReportResponse,
    TaskResponse,
    TaskRunRequest,
    TaskRunResponse,
    TaskRunStep,
    TaskStatus,
    TaskValidateInputsRequest,
    TaskValidateInputsResponse,
)
from backend.app.services.artifact_paths import (
    list_dry_run_record_specs,
    list_minimal_rnaseq_artifact_specs,
    list_placeholder_artifact_specs,
)
from backend.app.services.execution_adapter import (
    ExecutionResult,
    execute_task_minimal_rnaseq,
    execute_task_placeholder,
)
from backend.app.services.rnaseq_minimal import MinimalRNASeqValidationError
from backend.app.services.input_validation import (
    InputFileValidationResult,
    get_input_root,
    validate_rnaseq_input_files,
)
from backend.app.services.task_service import (
    append_lifecycle_event,
    create_task,
    get_task,
    update_task_status,
)


router = APIRouter(prefix="/task", tags=["task"])


def _get_registry_task_or_404(task_id: str) -> TaskRecord:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task


def _update_registry_status_or_404(
    task_id: str,
    status: TaskStatus,
    event_type: str,
    message: str,
) -> None:
    try:
        task = update_task_status(
            task_id=task_id,
            status=status,
            event_type=event_type,
            message=message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


def _audit_timestamp(task: TaskRecord, event_index: int) -> str:
    created_at = datetime.fromisoformat(task.created_at.replace("Z", "+00:00"))
    timestamp = created_at + timedelta(seconds=event_index)
    return timestamp.isoformat().replace("+00:00", "Z")


def _safe_relative_path(result: InputFileValidationResult) -> str | None:
    if result.resolved_path is None:
        return None

    try:
        return result.resolved_path.relative_to(get_input_root()).as_posix()
    except ValueError:
        return None


def _input_file_response(
    result: InputFileValidationResult,
) -> TaskInputFileValidationResponse:
    return TaskInputFileValidationResponse(
        safe_relative_path=_safe_relative_path(result),
        exists=result.exists,
        suffix=result.suffix,
        valid=result.valid,
        errors=result.errors,
    )


def _run_artifacts(execution_result: ExecutionResult) -> list[dict]:
    return [
        {
            "name": artifact["name"],
            "artifact_type": artifact["artifact_type"],
            "path": artifact["relative_path"],
            "available": artifact["exists"],
            "executor_name": execution_result.executor_name,
            "description": artifact["description"],
        }
        for artifact in [
            *execution_result.planned_artifacts,
            *execution_result.generated_files,
        ]
    ]


def _artifact_specs_for_response(task_id: str) -> list[dict]:
    minimal_artifacts = list_minimal_rnaseq_artifact_specs(task_id)
    if any(
        artifact["name"] == "normalized_counts_cpm.csv" and artifact["exists"]
        for artifact in minimal_artifacts
    ):
        return minimal_artifacts

    return [
        *list_placeholder_artifact_specs(task_id),
        *[
            artifact
            for artifact in list_dry_run_record_specs(task_id)
            if artifact["exists"]
        ],
    ]


def _is_minimal_real_run_request(request: TaskRunRequest) -> bool:
    return (
        request.execution_mode == "minimal_real"
        or bool(request.metadata_file and request.count_matrix_file)
    )


def _validate_run_mode_request(request: TaskRunRequest) -> None:
    if request.execution_mode not in (None, "dry_run", "placeholder", "minimal_real"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported execution_mode: {request.execution_mode}",
        )

    if request.execution_mode == "minimal_real" and (
        not request.metadata_file or not request.count_matrix_file
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "metadata_file and count_matrix_file are both required "
                "for minimal_real execution."
            ),
        )

    if (request.metadata_file and not request.count_matrix_file) or (
        request.count_matrix_file and not request.metadata_file
    ):
        raise HTTPException(
            status_code=400,
            detail="metadata_file and count_matrix_file must be supplied together.",
        )


def _minimal_artifacts_exist(task_id: str) -> bool:
    return any(
        artifact["name"] == "normalized_counts_cpm.csv" and artifact["exists"]
        for artifact in list_minimal_rnaseq_artifact_specs(task_id)
    )


def _ensure_can_mark_run_ready(task: TaskRecord) -> None:
    if task.status != TaskStatus.QC_PLACEHOLDER_READY:
        raise HTTPException(
            status_code=409,
            detail=(
                "Invalid task status transition: "
                f"{task.status.value} -> {TaskStatus.RUN_PLACEHOLDER_READY.value}"
            ),
        )


def _append_minimal_validation_failed_event(
    task_id: str,
    exc: MinimalRNASeqValidationError,
) -> None:
    append_lifecycle_event(
        task_id=task_id,
        event_type="minimal_analysis_validation_failed",
        message="Minimal real Bulk RNA-seq input validation failed.",
        metadata={
            "error_code": exc.error_code,
            "error_count": len(exc.errors),
        },
    )


@router.post("/create", response_model=TaskResponse)
def create_task_endpoint(request: TaskCreateRequest | None = None) -> TaskResponse:
    task = create_task(request or TaskCreateRequest())
    return TaskResponse(task_id=task.task_id, status=task.status, message=task.message)


@router.post("/validate-inputs", response_model=TaskValidateInputsResponse)
def validate_task_inputs(request: TaskValidateInputsRequest) -> TaskValidateInputsResponse:
    validation = validate_rnaseq_input_files(
        metadata_file=request.metadata_file,
        count_matrix_file=request.count_matrix_file,
    )

    return TaskValidateInputsResponse(
        status="input_validation_completed",
        valid=validation.valid,
        metadata=_input_file_response(validation.metadata),
        count_matrix=_input_file_response(validation.count_matrix),
        errors=validation.errors,
        limitations=validation.limitations,
    )


@router.post("/plan", response_model=AnalysisPlanResponse, response_model_exclude_none=True)
def create_analysis_plan(request: AnalysisPlanRequest) -> AnalysisPlanResponse:
    if request.task_id is not None:
        _update_registry_status_or_404(
            task_id=request.task_id,
            status=TaskStatus.PLANNED,
            event_type="plan_generated",
            message="Placeholder analysis plan generated and task status updated.",
        )

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
    if request.task_id is not None:
        _update_registry_status_or_404(
            task_id=request.task_id,
            status=TaskStatus.QC_PLACEHOLDER_READY,
            event_type="qc_checked",
            message="Placeholder QC checks generated and task status updated.",
        )

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
    _validate_run_mode_request(request)
    is_minimal_real_run = _is_minimal_real_run_request(request)

    task = _get_registry_task_or_404(request.task_id)

    if is_minimal_real_run:
        _ensure_can_mark_run_ready(task)
        try:
            execution_result = execute_task_minimal_rnaseq(
                task_id=request.task_id,
                metadata_file=request.metadata_file or "",
                count_matrix_file=request.count_matrix_file or "",
                registry_record=task,
                project_name=request.project_name,
                omics_type=request.omics_type,
            )
        except MinimalRNASeqValidationError as exc:
            _append_minimal_validation_failed_event(request.task_id, exc)
            raise HTTPException(status_code=422, detail=exc.to_detail()) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Minimal RNA-seq execution failed.",
            ) from exc

        _update_registry_status_or_404(
            task_id=request.task_id,
            status=TaskStatus.RUN_PLACEHOLDER_READY,
            event_type="minimal_rnaseq_executed",
            message="Minimal real Bulk RNA-seq MVP execution completed and task status updated.",
        )
        return TaskRunResponse(
            task_id=request.task_id,
            project_name=request.project_name,
            status="minimal_analysis_completed",
            run_steps=[
                TaskRunStep(
                    step_id="run_1",
                    name="Validate and load inputs",
                    status="completed",
                    message="Input paths were validated and tabular files were parsed.",
                ),
                TaskRunStep(
                    step_id="run_2",
                    name="Compute basic QC metrics",
                    status="completed",
                    message="Library sizes, sample counts, condition counts, and low-count filtering were computed.",
                ),
                TaskRunStep(
                    step_id="run_3",
                    name="Compute preliminary ranking",
                    status="completed",
                    message="CPM normalization and preliminary log2 fold-change ranking were computed without statistical testing.",
                ),
            ],
            artifacts=_run_artifacts(execution_result),
            limitations=execution_result.limitations,
        )

    _update_registry_status_or_404(
        task_id=request.task_id,
        status=TaskStatus.RUN_PLACEHOLDER_READY,
        event_type="run_placeholder_executed",
        message=(
            "Placeholder run executed and task status updated. "
            "No real RNA-seq analysis was performed."
        ),
    )
    try:
        execution_result = execute_task_placeholder(
            task_id=request.task_id,
            registry_record=task,
            project_name=request.project_name,
            omics_type=request.omics_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        artifacts=_run_artifacts(execution_result),
        limitations=[
            *execution_result.limitations,
            "This endpoint does not run real RNA-seq analysis.",
            "No biological result files are read or written.",
            "No statistical or biological conclusion should be drawn from this placeholder response.",
        ],
    )


@router.get("/{task_id}/report", response_model=TaskReportResponse)
def get_task_report(task_id: str) -> TaskReportResponse:
    _update_registry_status_or_404(
        task_id=task_id,
        status=TaskStatus.REPORT_PLACEHOLDER_READY,
        event_type="report_placeholder_generated",
        message=(
            "Placeholder report generated and task status updated. "
            "No real report file was created."
        ),
    )

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
    task = _get_registry_task_or_404(task_id)
    if task.status == TaskStatus.REPORT_PLACEHOLDER_READY:
        _update_registry_status_or_404(
            task_id=task_id,
            status=TaskStatus.ARTIFACTS_PLACEHOLDER_READY,
            event_type="artifacts_placeholder_listed",
            message=(
                "Placeholder artifacts listed and task status updated. "
                "No real files were generated."
            ),
        )
    elif task.status == TaskStatus.RUN_PLACEHOLDER_READY and not _minimal_artifacts_exist(task_id):
        _update_registry_status_or_404(
            task_id=task_id,
            status=TaskStatus.ARTIFACTS_PLACEHOLDER_READY,
            event_type="artifacts_placeholder_listed",
            message=(
                "Placeholder artifacts listed and task status updated. "
                "No real files were generated."
            ),
        )
    elif task.status not in (
        TaskStatus.ARTIFACTS_PLACEHOLDER_READY,
        TaskStatus.RUN_PLACEHOLDER_READY,
    ):
        _update_registry_status_or_404(
            task_id=task_id,
            status=TaskStatus.ARTIFACTS_PLACEHOLDER_READY,
            event_type="artifacts_placeholder_listed",
            message=(
                "Placeholder artifacts listed and task status updated. "
                "No real files were generated."
            ),
        )

    return TaskArtifactsResponse(
        task_id=task_id,
        status="artifacts_placeholder_ready",
        artifacts=[
            TaskArtifact(
                artifact_id=f"artifact_{index}",
                name=artifact["name"],
                artifact_type=artifact["artifact_type"],
                path=artifact["relative_path"],
                description=artifact["description"],
                available=artifact["exists"],
            )
            for index, artifact in enumerate(_artifact_specs_for_response(task_id), start=1)
        ],
        limitations=[
            (
                "This endpoint lists planned safe relative artifact paths "
                "and existing dry-run record files."
            ),
            "This endpoint does not create or write real artifact files.",
            "Real artifact generation will be implemented in a later phase.",
        ],
    )


@router.get("/{task_id}/audit", response_model=TaskAuditResponse)
def get_task_audit(task_id: str) -> TaskAuditResponse:
    task = _get_registry_task_or_404(task_id)

    return TaskAuditResponse(
        task_id=task_id,
        status="audit_placeholder_ready",
        events=[
            AuditEvent(
                event_id=f"audit_{index + 1}",
                event_type=event.event_type,
                message=event.message,
                timestamp=_audit_timestamp(task, index),
                actor=event.actor,
                metadata=event.metadata,
            )
            for index, event in enumerate(task.lifecycle_events)
        ],
        limitations=[
            "This endpoint returns deterministic placeholder registry lifecycle events.",
            "This endpoint reads process-local in-memory task lifecycle history only.",
            "No database or durable audit storage is implemented yet.",
            "No real execution logs are read.",
            "No real files are generated.",
        ],
    )


@router.get("/{task_id}/status", response_model=TaskResponse)
def get_task_status(task_id: str) -> TaskResponse:
    task = _get_registry_task_or_404(task_id)
    return TaskResponse(task_id=task.task_id, status=task.status, message=task.message)
