import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from backend.app.api.routes_run import execute_project_run
from backend.app.config import get_settings
from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.coze import (
    CozeConfirmAndRunRequest,
    CozeConfirmAndRunResponse,
    CozeCreateProjectRequest,
    CozeCreateProjectResponse,
    CozeInspectRequest,
    CozeInspectResponse,
    CozePrepareAnalysisRequest,
    CozePrepareAnalysisResponse,
    CozeReportResponse,
    CozeStatusResponse,
)
from backend.app.models.project import ProjectStatus
from backend.app.models.qc_report import QCSeverity, QCStatus
from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.reports.evidence_package import allowed_conclusion_level
from backend.app.services.artifact_service import STORE
from backend.app.services.export_package import load_existing_export_metadata
from backend.app.services.file_inspector import inspect_file
from backend.app.services.plan_service import create_recommended_plan
from backend.app.services.qc_service import run_qc
from backend.app.services.report_summary import build_report_review_summary
from backend.app.services.result_interpretation import build_result_interpretation
from backend.app.services.schema_detector import detect_schema


router = APIRouter(prefix="/coze", tags=["coze"])


@router.post("/projects", response_model=CozeCreateProjectResponse)
def coze_create_project(request: CozeCreateProjectRequest) -> CozeCreateProjectResponse:
    if request.omics_type != "bulk_rnaseq" or request.input_level != "count_matrix":
        raise HTTPException(status_code=400, detail="Phase 1 Coze adapter supports only bulk_rnaseq count_matrix.")
    project = STORE.create_project(
        name=request.project_name,
        description="Created from Coze adapter.",
        omics_type=request.omics_type,
    )
    STORE.project_metadata[project.project_id] = {
        "input_level": request.input_level,
        "organism": request.organism,
        "gene_id_type": request.gene_id_type,
        "annotation_version": request.annotation_version,
    }
    return CozeCreateProjectResponse(
        project_id=project.project_id,
        human_readable_summary=f"Project created for {request.omics_type} {request.input_level} analysis.",
        next_action="upload_or_register_files",
    )


@router.post("/projects/{project_id}/inspect", response_model=CozeInspectResponse)
def coze_inspect(project_id: str, request: CozeInspectRequest) -> CozeInspectResponse:
    _require_project(project_id)
    warnings: List[str] = []
    try:
        count_matrix = inspect_file(request.count_matrix_path)
        metadata = inspect_file(request.metadata_path)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "validation_issues": [
                    {
                        "severity": "error",
                        "code": "INPUT_FILE_UNREADABLE",
                        "message": "One or more input files are missing or cannot be read.",
                        "suggestion": "Check the count_matrix_path and metadata_path values and ensure both files exist.",
                        "details": {
                            "count_matrix_path": request.count_matrix_path,
                            "metadata_path": request.metadata_path,
                            "error": str(exc),
                        },
                    }
                ]
            },
        ) from exc

    STORE.register_files(project_id, request.count_matrix_path, request.metadata_path)
    detected = detect_schema(count_matrix=count_matrix, metadata=metadata)
    STORE.inspections[project_id] = {
        "project_id": project_id,
        "count_matrix": _model_to_dict(count_matrix),
        "metadata": _model_to_dict(metadata),
        "detected_schema": detected,
    }
    STORE.update_status(project_id, ProjectStatus.INSPECTED)

    possible_batch_column = _possible_batch_column(metadata.columns)
    if not detected["recommended"].get("sample_id_column"):
        warnings.append("No obvious sample ID column was detected.")
    if not detected["recommended"].get("group_column"):
        warnings.append("No obvious group column was detected.")
    validation_issues = _inspect_validation_issues(
        count_matrix_columns=count_matrix.columns,
        count_matrix_rows=count_matrix.row_count,
        metadata_columns=metadata.columns,
        metadata_rows=metadata.row_count,
        sample_columns=detected["count_matrix"].get("sample_columns", []),
        sample_id_column=detected["recommended"].get("sample_id_column"),
        group_column=detected["recommended"].get("group_column"),
        gene_id_column=detected["recommended"].get("gene_id_column"),
    )

    return CozeInspectResponse(
        project_id=project_id,
        gene_id_column_candidates=detected["count_matrix"].get("gene_id_column_candidates", []),
        sample_columns=detected["count_matrix"].get("sample_columns", []),
        metadata_columns=metadata.columns,
        possible_sample_id_column=detected["recommended"].get("sample_id_column"),
        possible_group_column=detected["recommended"].get("group_column"),
        possible_batch_column=possible_batch_column,
        warnings=warnings,
        validation_issues=validation_issues,
        human_readable_summary="Files were registered and inspected. Please confirm schema mapping and contrast.",
        next_action="confirm_schema_mapping",
    )


@router.post("/projects/{project_id}/prepare-analysis", response_model=CozePrepareAnalysisResponse)
def coze_prepare_analysis(project_id: str, request: CozePrepareAnalysisRequest) -> CozePrepareAnalysisResponse:
    _require_project(project_id)
    files = _require_files(project_id)
    metadata = STORE.project_metadata.get(project_id, {})
    config = BulkRNASeqAnalysisConfig(
        project_id=project_id,
        count_matrix_file=files["count_matrix_file"],
        metadata_file=files["metadata_file"],
        sample_id_column=request.sample_id_column,
        gene_id_column=request.gene_id_column,
        group_column=request.group_column,
        reference_group=request.reference_group,
        test_group=request.test_group,
        batch_column=request.batch_column,
        covariates=request.covariates,
        organism=metadata.get("organism"),
        gene_id_type=metadata.get("gene_id_type"),
        annotation_version=metadata.get("annotation_version"),
        fdr_threshold=request.fdr_threshold,
        log2fc_threshold=request.log2fc_threshold,
    )
    qc_report = run_qc(config)
    STORE.analysis_configs[project_id] = config
    STORE.qc_reports[project_id] = qc_report
    STORE.update_status(project_id, ProjectStatus.QC_COMPLETED)
    stop_conditions = _stop_conditions(qc_report)
    warnings = _warnings(qc_report)

    if stop_conditions:
        return CozePrepareAnalysisResponse(
            project_id=project_id,
            qc_status="fail",
            stop_conditions=stop_conditions,
            warnings=warnings,
            validation_issues=[_model_to_dict(issue) for issue in qc_report.validation_issues],
            recommended_plan=None,
            requires_user_confirmation=True,
            human_readable_summary="QC found critical stop conditions. Please fix inputs or schema mapping before running analysis.",
            next_action="fix_input",
        )

    plan = create_recommended_plan(config=config, qc_report=qc_report)
    STORE.plans[project_id] = plan
    STORE.update_status(project_id, ProjectStatus.PLAN_PROPOSED)
    return CozePrepareAnalysisResponse(
        project_id=project_id,
        qc_status="warn" if warnings else "pass",
        stop_conditions=[],
        warnings=warnings,
        validation_issues=[_model_to_dict(issue) for issue in qc_report.validation_issues],
        recommended_plan=_model_to_dict(plan),
        requires_user_confirmation=plan.requires_user_confirmation,
        human_readable_summary="QC passed and a recommended analysis plan is ready for user confirmation.",
        next_action="confirm_and_run",
    )


@router.post("/projects/{project_id}/confirm-and-run", response_model=CozeConfirmAndRunResponse)
def coze_confirm_and_run(project_id: str, request: CozeConfirmAndRunRequest) -> CozeConfirmAndRunResponse:
    _require_project(project_id)
    if not request.confirmed:
        return CozeConfirmAndRunResponse(
            project_id=project_id,
            run_status="skipped",
            reliability_grade=None,
            allowed_conclusion_level="No scientific conclusion.",
            human_readable_summary="User did not confirm the analysis plan. No analysis was run.",
            artifact_manifest=None,
            next_action="confirm_plan",
        )

    qc_report = STORE.qc_reports.get(project_id)
    if not qc_report:
        raise HTTPException(status_code=400, detail="Prepare analysis must be completed before confirm-and-run.")
    stop_conditions = _stop_conditions(qc_report)
    if stop_conditions:
        return CozeConfirmAndRunResponse(
            project_id=project_id,
            run_status="skipped",
            reliability_grade="E",
            allowed_conclusion_level=allowed_conclusion_level("E"),
            human_readable_summary="Analysis was not run because QC stop conditions are present.",
            artifact_manifest=_load_manifest(project_id),
            next_action="fix_input",
            stop_conditions=stop_conditions,
        )

    plan = STORE.plans.get(project_id)
    if not plan:
        raise HTTPException(status_code=400, detail="No recommended plan exists. Run prepare-analysis first.")
    plan = _apply_plan_overrides(plan, request.analysis_plan_overrides)
    plan = _copy_model(plan, {"confirmed": True})
    STORE.plans[project_id] = plan
    STORE.update_status(project_id, ProjectStatus.PLAN_CONFIRMED)

    run_response = execute_project_run(
        project_id=project_id,
        plan_id=plan.plan_id,
        run_mode_override=request.run_mode,
    )
    manifest = _load_manifest(project_id)
    grade = run_response.reliability.grade.value
    return CozeConfirmAndRunResponse(
        project_id=project_id,
        run_status=run_response.status.value,
        reliability_grade=grade,
        allowed_conclusion_level=allowed_conclusion_level(grade),
        human_readable_summary=_run_summary(run_response.status.value, grade),
        artifact_manifest=manifest,
        artifact_paths=_present_artifact_paths(manifest),
        next_action="review_report",
        warnings=run_response.reliability.downgrade_conditions,
        stop_conditions=run_response.reliability.stop_conditions,
    )


@router.get("/projects/{project_id}/status", response_model=CozeStatusResponse)
def coze_status(project_id: str) -> CozeStatusResponse:
    project = _require_project(project_id)
    reliability = STORE.reliability.get(project_id)
    result = STORE.results.get(project_id, {})
    grade = reliability.grade.value if reliability else None
    run_status = project.status.value if project.status in {ProjectStatus.COMPLETED, ProjectStatus.FAILED} else None
    return CozeStatusResponse(
        project_id=project_id,
        status=project.status.value,
        current_stage=_current_stage(project.status.value),
        run_status=run_status,
        reliability_grade=grade,
        human_readable_summary=_status_summary(project.status.value, grade),
        next_action=_status_next_action(project.status.value),
    )


@router.get("/projects/{project_id}/report", response_model=CozeReportResponse)
def coze_report(project_id: str) -> CozeReportResponse:
    project = _require_project(project_id)
    artifact_root = _artifact_root(project_id)
    manifest = _load_manifest(project_id) or {}
    audit_log = _read_json(artifact_root / "10_audit_log.json")
    reliability = STORE.reliability.get(project_id)
    grade = reliability.grade.value if reliability else audit_log.get("reliability", {}).get("grade", "E")
    review = build_report_review_summary(
        project_id=project_id,
        status=project.status,
        reliability=reliability,
        result_summary=STORE.results.get(project_id, {}),
        manifest=manifest,
        audit_log=audit_log,
    )
    interpretation = build_result_interpretation(
        project_id=project_id,
        reliability=reliability,
        result_summary={"status": project.status.value, **STORE.results.get(project_id, {})},
        artifact_root=artifact_root,
    )
    return CozeReportResponse(
        project_id=project_id,
        summary_markdown=_read_text(artifact_root / "01_summary.md"),
        qc_report_markdown=_read_text(artifact_root / "02_qc_report.md"),
        method_selection_markdown=_read_text(artifact_root / "03_method_selection.md"),
        reliability_report_markdown=_read_text(artifact_root / "11_reliability_report.md"),
        audit_log=audit_log,
        artifact_manifest=manifest,
        allowed_conclusion_level=allowed_conclusion_level(grade),
        strong_conclusion_allowed=review["strong_conclusion_allowed"],
        final_status=review["final_status"],
        reliability_grade=review["reliability_grade"],
        primary_method_status=review["primary_method_status"],
        warnings=review["warnings"],
        errors=review["errors"],
        validation_consistency_score=review["validation_consistency_score"],
        artifact_presence_summary=review["artifact_presence_summary"],
        interpretation_summary=interpretation,
        top_genes=interpretation.get("top_genes", []),
        interpretation_guardrails=interpretation.get("guardrails", []),
        export_metadata=load_existing_export_metadata(project_id),
    )


def _require_project(project_id: str):
    try:
        return STORE.require_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc


def _require_files(project_id: str) -> Dict[str, str]:
    try:
        return STORE.get_files(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _possible_batch_column(columns: List[str]) -> Optional[str]:
    for column in columns:
        if "batch" in column.lower():
            return column
    return None


def _stop_conditions(qc_report) -> List[str]:
    return [
        check.message
        for check in qc_report.checks
        if check.status == QCStatus.FAIL and check.severity == QCSeverity.ERROR
    ]


def _warnings(qc_report) -> List[str]:
    return [
        check.message
        for check in qc_report.checks
        if check.status == QCStatus.WARN or check.severity == QCSeverity.WARNING
    ]


def _inspect_validation_issues(
    count_matrix_columns: List[str],
    count_matrix_rows: int,
    metadata_columns: List[str],
    metadata_rows: int,
    sample_columns: List[str],
    sample_id_column: Optional[str],
    group_column: Optional[str],
    gene_id_column: Optional[str],
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    if not gene_id_column:
        issues.append(
            _validation_issue(
                "error",
                "GENE_ID_COLUMN_NOT_DETECTED",
                "No likely gene ID column was detected in the count matrix.",
                "Confirm the gene_id_column manually before preparing analysis.",
                {"count_matrix_columns": count_matrix_columns},
            )
        )
    if gene_id_column and not sample_columns:
        issues.append(
            _validation_issue(
                "error",
                "COUNT_MATRIX_NO_SAMPLE_COLUMNS",
                "No sample count columns were detected in the count matrix.",
                "Ensure the count matrix has one gene ID column plus one column per sample.",
                {"gene_id_column": gene_id_column, "count_matrix_columns": count_matrix_columns},
            )
        )
    if count_matrix_rows == 0:
        issues.append(
            _validation_issue(
                "error",
                "COUNT_MATRIX_EMPTY",
                "Count matrix does not contain any gene rows.",
                "Provide a count matrix with one row per gene or feature.",
                {},
            )
        )
    if metadata_rows == 0:
        issues.append(
            _validation_issue(
                "error",
                "METADATA_EMPTY",
                "Metadata does not contain any sample rows.",
                "Provide one metadata row for each biological sample.",
                {},
            )
        )
    if not sample_id_column:
        issues.append(
            _validation_issue(
                "warning",
                "SAMPLE_ID_COLUMN_NOT_DETECTED",
                "No likely sample ID column was detected in metadata.",
                "Select the metadata column that exactly matches count matrix sample columns.",
                {"metadata_columns": metadata_columns},
            )
        )
    if not group_column:
        issues.append(
            _validation_issue(
                "warning",
                "GROUP_COLUMN_NOT_DETECTED",
                "No likely group column was detected in metadata.",
                "Select the metadata column containing biological group or condition labels.",
                {"metadata_columns": metadata_columns},
            )
        )
    return issues


def _validation_issue(
    severity: str,
    code: str,
    message: str,
    suggestion: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "suggestion": suggestion,
        "details": details,
    }


def _apply_plan_overrides(plan: AnalysisPlan, overrides: Dict[str, Any]) -> AnalysisPlan:
    allowed = {"fdr_threshold", "log2fc_threshold", "validation_methods", "enrichment"}
    update = {key: value for key, value in overrides.items() if key in allowed}
    return _copy_model(plan, update) if update else plan


def _copy_model(model, update: Dict[str, Any]):
    if hasattr(model, "model_copy"):
        return model.model_copy(update=update)
    return model.copy(update=update)


def _artifact_root(project_id: str) -> Path:
    return get_settings().project_root / "artifacts" / project_id


def _load_manifest(project_id: str) -> Optional[Dict[str, Any]]:
    path = _artifact_root(project_id) / "manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _present_artifact_paths(manifest: Optional[Dict[str, Any]]) -> List[str]:
    if not manifest:
        return []
    root = Path(manifest["artifact_root"])
    return [
        str(root / entry["relative_path"])
        for entry in manifest.get("files", [])
        if entry.get("status") == "present" and not entry["relative_path"].endswith("/")
    ]


def _current_stage(status: str) -> str:
    return {
        "created": "project_created",
        "files_uploaded": "files_registered",
        "inspected": "files_inspected",
        "qc_completed": "qc_completed",
        "plan_proposed": "plan_ready",
        "plan_confirmed": "plan_confirmed",
        "running": "analysis_running",
        "completed": "analysis_completed",
        "failed": "analysis_failed",
    }.get(status, status)


def _status_next_action(status: str) -> str:
    return {
        "created": "upload_or_register_files",
        "files_uploaded": "inspect_files",
        "inspected": "confirm_schema_mapping",
        "qc_completed": "review_qc",
        "plan_proposed": "confirm_and_run",
        "plan_confirmed": "run_analysis",
        "running": "poll_status",
        "completed": "review_report",
        "failed": "review_report",
    }.get(status, "review_project")


def _status_summary(status: str, grade: Optional[str]) -> str:
    if status == "completed":
        return f"Analysis completed with reliability grade {grade}."
    if status == "failed":
        return f"Analysis failed with reliability grade {grade}."
    return f"Project status is {status}."


def _run_summary(status: str, grade: str) -> str:
    if status == "completed":
        return f"Analysis completed. Reliability grade is {grade}."
    return f"Analysis did not complete successfully. Reliability grade is {grade}."


def _model_to_dict(model) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
