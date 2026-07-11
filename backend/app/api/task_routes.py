from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.models.task import (
    AnalysisPlanRequest,
    AnalysisPlanResponse,
    AnalysisStep,
    AuditEvent,
    FormalDEPreflightChecks,
    FormalDEPreflightResponse,
    QCCheck,
    QCRequest,
    QCResponse,
    ReportSection,
    TaskArtifact,
    TaskArtifactsResponse,
    TaskAuditResponse,
    TaskCreateRequest,
    TaskInputFileValidationResponse,
    TaskInputRegisterRequest,
    TaskInputRegistrationResponse,
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
    list_deseq2_artifact_specs,
    list_dry_run_record_specs,
    list_minimal_rnaseq_artifact_specs,
    list_placeholder_artifact_specs,
)
from backend.app.services.artifact_download import (
    ArtifactDownloadError,
    get_artifact_download_payload,
)
from backend.app.services.coze_summary import (
    CozeSummaryError,
    build_coze_task_summary,
)
from backend.app.services.contrast_validation import ContrastValidationError
from backend.app.services.deseq2_execution import (
    DESEQ2_ANALYSIS_METHOD,
    Deseq2ExecutionError,
    execute_task_deseq2,
)
from backend.app.services.execution_adapter import (
    ExecutionResult,
    execute_task_minimal_rnaseq,
    execute_task_placeholder,
)
from backend.app.services.execution_trace import begin_execution_trace
from backend.app.services.execution_trace import complete_execution_trace
from backend.app.services.execution_trace import fail_execution_trace
from backend.app.services.execution_trace import trace_metadata
from backend.app.services.rnaseq_minimal import (
    MinimalRNASeqValidationError,
    RNASeqMethodContractError,
    validate_requested_analysis_method,
    validate_requested_formal_de_method,
)
from backend.app.services import formal_de_preflight
from backend.app.services.input_validation import (
    InputFileValidationResult,
    get_input_root,
    validate_rnaseq_input_files,
)
from backend.app.services.task_inputs import (
    TaskInputRegistrationError,
    registered_input_paths_for_run,
    register_task_input,
)
from backend.app.services.task_service import (
    append_lifecycle_event,
    create_task,
    get_task,
    save_task_artifacts,
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
    metadata: dict | None = None,
) -> None:
    try:
        task = update_task_status(
            task_id=task_id,
            status=status,
            event_type=event_type,
            message=message,
            metadata=metadata,
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
    deseq2_artifacts = list_deseq2_artifact_specs(task_id)
    if any(
        artifact["name"] == "deseq2_results.csv" and artifact["exists"]
        for artifact in deseq2_artifacts
    ):
        return deseq2_artifacts

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


def _normalize_method_name(method: object) -> str:
    return "" if method is None else str(method).strip().lower()


def _is_deseq2_run_request(request: TaskRunRequest) -> bool:
    return DESEQ2_ANALYSIS_METHOD in {
        _normalize_method_name(request.analysis_method),
        _normalize_method_name(request.formal_de_method),
    }


def _is_minimal_real_run_request(request: TaskRunRequest) -> bool:
    return (
        request.execution_mode == "minimal_real"
        or bool(request.metadata_file and request.count_matrix_file)
    )


def _validate_run_mode_request(request: TaskRunRequest) -> None:
    if request.execution_mode not in (
        None,
        "dry_run",
        "placeholder",
        "minimal_real",
        "formal_de_real",
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported execution_mode: {request.execution_mode}",
        )

    if request.execution_mode in ("minimal_real", "formal_de_real") and (
        not request.metadata_file or not request.count_matrix_file
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "metadata_file and count_matrix_file are both required "
                f"for {request.execution_mode} execution."
            ),
        )

    if (request.metadata_file and not request.count_matrix_file) or (
        request.count_matrix_file and not request.metadata_file
    ):
        raise HTTPException(
            status_code=400,
            detail="metadata_file and count_matrix_file must be supplied together.",
        )

    if request.execution_mode == "formal_de_real" and not _is_deseq2_run_request(request):
        raise HTTPException(
            status_code=400,
            detail=(
                "formal_de_real execution currently requires analysis_method "
                "or formal_de_method to be 'deseq2'."
            ),
        )

    try:
        validate_requested_analysis_method(request.analysis_method)
        validate_requested_formal_de_method(request.formal_de_method)
    except RNASeqMethodContractError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc


def _minimal_artifacts_exist(task_id: str) -> bool:
    return any(
        artifact["name"] == "normalized_counts_cpm.csv" and artifact["exists"]
        for artifact in list_minimal_rnaseq_artifact_specs(task_id)
    )


def _deseq2_artifacts_exist(task_id: str) -> bool:
    return any(
        artifact["name"] == "deseq2_results.csv" and artifact["exists"]
        for artifact in list_deseq2_artifact_specs(task_id)
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
    trace: object | None = None,
) -> None:
    metadata = {
        "error_code": exc.error_code,
        "error_count": len(exc.errors),
    }
    if trace is not None:
        metadata["execution_trace"] = trace_metadata(trace)
    append_lifecycle_event(
        task_id=task_id,
        event_type="minimal_analysis_validation_failed",
        message="Minimal real Bulk RNA-seq input validation failed.",
        metadata=metadata,
    )


def _record_execution_failure(task_id: str, trace, reason: str) -> None:
    failed_trace = fail_execution_trace(trace, reason)
    append_lifecycle_event(
        task_id=task_id,
        event_type="analysis_failed",
        message="Analysis execution failed. See sanitized trace metadata.",
        metadata={"execution_trace": trace_metadata(failed_trace)},
    )


def _copy_run_request_with_inputs(
    request: TaskRunRequest,
    *,
    metadata_file: str,
    count_matrix_file: str,
) -> TaskRunRequest:
    updates = {
        "metadata_file": metadata_file,
        "count_matrix_file": count_matrix_file,
    }
    if hasattr(request, "model_copy"):
        return request.model_copy(update=updates)
    return request.copy(update=updates)


def _apply_registered_inputs_to_run_request(request: TaskRunRequest) -> TaskRunRequest:
    if request.metadata_file or request.count_matrix_file:
        return request

    registered_metadata, registered_count_matrix = registered_input_paths_for_run(
        request.task_id
    )
    if not registered_metadata and not registered_count_matrix:
        return request

    if not registered_metadata or not registered_count_matrix:
        raise HTTPException(
            status_code=400,
            detail="Both metadata and count matrix inputs are required.",
        )

    return _copy_run_request_with_inputs(
        request,
        metadata_file=registered_metadata,
        count_matrix_file=registered_count_matrix,
    )


@router.post(
    "/create",
    response_model=TaskResponse,
    operation_id="coze_create_analysis_task",
    summary="Create analysis task",
    description="Create a task record and return its stable task identifier.",
    openapi_extra={"x-coze-operation": "create_analysis_task"},
)
def create_task_endpoint(request: TaskCreateRequest | None = None) -> TaskResponse:
    task = create_task(request or TaskCreateRequest())
    return TaskResponse(task_id=task.task_id, status=task.status, message=task.message)


@router.post(
    "/validate-inputs",
    response_model=TaskValidateInputsResponse,
    operation_id="coze_validate_analysis_inputs",
    summary="Validate analysis inputs",
    description="Validate metadata and count-matrix inputs without running analysis.",
    openapi_extra={"x-coze-operation": "validate_input"},
)
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


@router.get("/formal-de/preflight", response_model=FormalDEPreflightResponse)
def get_formal_de_preflight() -> FormalDEPreflightResponse:
    preflight = formal_de_preflight.run_deseq2_preflight()
    return FormalDEPreflightResponse(
        formal_method=preflight["formal_method"],
        ready=preflight["ready"],
        checks=FormalDEPreflightChecks(
            r_available=preflight["r_available"],
            rscript_available=preflight["rscript_available"],
            r_version=preflight["r_version"],
            rscript_version=preflight["rscript_version"],
            biocmanager_available=preflight["biocmanager_available"],
            deseq2_available=preflight["deseq2_available"],
            checked_at=preflight["checked_at"],
            commands_checked=preflight["commands_checked"],
        ),
        warnings=preflight["warnings"],
        errors=preflight["errors"],
        limitations=preflight["limitations"],
    )


@router.get(
    "/{task_id}/coze-summary",
    operation_id="coze_retrieve_result_summary",
    summary="Retrieve safe result summary",
    description=(
        "Return a concise task-scoped result and artifact summary with explicit "
        "scientific limitations and relative download links."
    ),
    openapi_extra={"x-coze-operation": "retrieve_summary"},
)
def get_task_coze_summary(task_id: str) -> dict:
    try:
        return build_coze_task_summary(task_id)
    except CozeSummaryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.post(
    "/{task_id}/inputs/register",
    response_model=TaskInputRegistrationResponse,
    operation_id="coze_register_analysis_input",
    summary="Register task input metadata",
    description="Register one task-scoped input using a safe relative source path.",
    openapi_extra={"x-coze-operation": "submit_input_metadata"},
)
def register_task_input_endpoint(
    task_id: str,
    request: TaskInputRegisterRequest,
) -> TaskInputRegistrationResponse:
    try:
        payload = register_task_input(
            task_id=task_id,
            input_role=request.input_role,
            source_relative_path=request.source_relative_path,
        )
    except TaskInputRegistrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return TaskInputRegistrationResponse(**payload)


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


@router.post(
    "/run",
    response_model=TaskRunResponse,
    operation_id="coze_run_analysis_task",
    summary="Run analysis task",
    description="Run the requested task workflow after required preparation and validation.",
    openapi_extra={"x-coze-operation": "run_analysis"},
)
def run_task_placeholder(request: TaskRunRequest) -> TaskRunResponse:
    task = _get_registry_task_or_404(request.task_id)
    request = _apply_registered_inputs_to_run_request(request)
    _validate_run_mode_request(request)
    is_deseq2_run = _is_deseq2_run_request(request)
    is_minimal_real_run = _is_minimal_real_run_request(request) and not is_deseq2_run
    _ensure_can_mark_run_ready(task)
    execution_trace = begin_execution_trace(
        request.task_id,
        "analysis_execution",
        {
            "execution_mode": request.execution_mode or "placeholder",
            "analysis_method": request.analysis_method or "unspecified",
            "formal_de_method": request.formal_de_method or "unspecified",
        },
    )

    if is_deseq2_run:
        try:
            execution_result = execute_task_deseq2(
                task_id=request.task_id,
                metadata_file=request.metadata_file or "",
                count_matrix_file=request.count_matrix_file or "",
                project_name=request.project_name,
                omics_type=request.omics_type,
                contrast_column=request.contrast_column,
                contrast_numerator=request.contrast_numerator,
                contrast_denominator=request.contrast_denominator,
            )
        except MinimalRNASeqValidationError as exc:
            _record_execution_failure(
                request.task_id, execution_trace, "input_validation_failed"
            )
            raise HTTPException(status_code=422, detail=exc.to_detail()) from exc
        except ContrastValidationError as exc:
            _record_execution_failure(
                request.task_id, execution_trace, "contrast_validation_failed"
            )
            raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
        except Deseq2ExecutionError as exc:
            _record_execution_failure(
                request.task_id, execution_trace, "formal_execution_failed"
            )
            raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc

        complete_execution_trace(execution_trace)
        _update_registry_status_or_404(
            task_id=request.task_id,
            status=TaskStatus.RUN_PLACEHOLDER_READY,
            event_type="deseq2_executed",
            message="DESeq2 formal differential expression execution completed and task status updated.",
        )
        artifacts = _run_artifacts(execution_result)
        save_task_artifacts(request.task_id, artifacts)
        return TaskRunResponse(
            task_id=request.task_id,
            project_name=request.project_name,
            status="deseq2_analysis_completed",
            run_steps=[
                TaskRunStep(
                    step_id="run_1",
                    name="Validate and load inputs",
                    status="completed",
                    message="Input paths and RNA-seq content were validated.",
                ),
                TaskRunStep(
                    step_id="run_2",
                    name="Check DESeq2 preflight",
                    status="completed",
                    message="Rscript and DESeq2 preflight readiness was confirmed.",
                ),
                TaskRunStep(
                    step_id="run_3",
                    name="Run DESeq2",
                    status="completed",
                    message="DESeq2 was run with design formula ~ condition.",
                ),
                TaskRunStep(
                    step_id="run_4",
                    name="Collect formal outputs",
                    status="completed",
                    message="DESeq2 results, summary, manifest, and report artifacts were written.",
                ),
            ],
            artifacts=artifacts,
            limitations=execution_result.limitations,
        )

    if is_minimal_real_run:
        try:
            execution_result = execute_task_minimal_rnaseq(
                task_id=request.task_id,
                metadata_file=request.metadata_file or "",
                count_matrix_file=request.count_matrix_file or "",
                registry_record=task,
                project_name=request.project_name,
                omics_type=request.omics_type,
                contrast_column=request.contrast_column,
                contrast_numerator=request.contrast_numerator,
                contrast_denominator=request.contrast_denominator,
            )
        except MinimalRNASeqValidationError as exc:
            fail_execution_trace(execution_trace, "input_validation_failed")
            _append_minimal_validation_failed_event(
                request.task_id, exc, execution_trace
            )
            raise HTTPException(status_code=422, detail=exc.to_detail()) from exc
        except ContrastValidationError as exc:
            _record_execution_failure(
                request.task_id, execution_trace, "contrast_validation_failed"
            )
            raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
        except ValueError as exc:
            _record_execution_failure(
                request.task_id, execution_trace, "execution_failed"
            )
            raise HTTPException(
                status_code=400,
                detail="Minimal RNA-seq execution failed.",
            ) from exc

        complete_execution_trace(execution_trace)
        _update_registry_status_or_404(
            task_id=request.task_id,
            status=TaskStatus.RUN_PLACEHOLDER_READY,
            event_type="minimal_rnaseq_executed",
            message="Minimal real Bulk RNA-seq MVP execution completed and task status updated.",
        )
        artifacts = _run_artifacts(execution_result)
        save_task_artifacts(request.task_id, artifacts)
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
            artifacts=artifacts,
            limitations=execution_result.limitations,
        )

    try:
        execution_result = execute_task_placeholder(
            task_id=request.task_id,
            registry_record=task,
            project_name=request.project_name,
            omics_type=request.omics_type,
        )
    except ValueError as exc:
        _record_execution_failure(
            request.task_id, execution_trace, "execution_failed"
        )
        raise HTTPException(
            status_code=400, detail="Placeholder execution failed."
        ) from exc

    complete_execution_trace(execution_trace)
    _update_registry_status_or_404(
        task_id=request.task_id,
        status=TaskStatus.RUN_PLACEHOLDER_READY,
        event_type="run_placeholder_executed",
        message=(
            "Placeholder run executed and task status updated. "
            "No real RNA-seq analysis was performed."
        ),
    )
    artifacts = _run_artifacts(execution_result)
    save_task_artifacts(request.task_id, artifacts)
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
        artifacts=artifacts,
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


@router.get(
    "/{task_id}/artifacts",
    response_model=TaskArtifactsResponse,
    operation_id="coze_list_task_artifacts",
    summary="List task artifacts",
    description="List task-scoped artifact metadata and safe relative references.",
    openapi_extra={"x-coze-operation": "retrieve_artifacts"},
)
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
    elif (
        task.status == TaskStatus.RUN_PLACEHOLDER_READY
        and not _minimal_artifacts_exist(task_id)
        and not _deseq2_artifacts_exist(task_id)
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

    artifact_payloads = [
        {
            "artifact_id": f"artifact_{index}",
            "name": artifact["name"],
            "artifact_type": artifact["artifact_type"],
            "path": artifact["relative_path"],
            "description": artifact["description"],
            "available": artifact["exists"],
        }
        for index, artifact in enumerate(_artifact_specs_for_response(task_id), start=1)
    ]
    save_task_artifacts(task_id, artifact_payloads)

    return TaskArtifactsResponse(
        task_id=task_id,
        status="artifacts_placeholder_ready",
        artifacts=[TaskArtifact(**artifact) for artifact in artifact_payloads],
        limitations=[
            (
                "This endpoint lists planned safe relative artifact paths "
                "and existing dry-run record files."
            ),
            "This endpoint does not create or write real artifact files.",
            "Real artifact generation will be implemented in a later phase.",
        ],
    )


@router.get("/{task_id}/artifacts/{artifact_name:path}/download")
def download_task_artifact(task_id: str, artifact_name: str) -> FileResponse:
    try:
        payload = get_artifact_download_payload(task_id, artifact_name)
    except ArtifactDownloadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None

    return FileResponse(
        payload.path,
        media_type=payload.media_type,
        filename=payload.filename,
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


@router.get(
    "/{task_id}/status",
    response_model=TaskResponse,
    operation_id="coze_query_task_status",
    summary="Query task status",
    description="Return the current task lifecycle status and concise status message.",
    openapi_extra={"x-coze-operation": "query_task_status"},
)
def get_task_status(task_id: str) -> TaskResponse:
    task = _get_registry_task_or_404(task_id)
    return TaskResponse(task_id=task.task_id, status=task.status, message=task.message)
