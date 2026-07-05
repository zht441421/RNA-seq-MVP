from typing import Any, Dict, List, Optional
from pathlib import Path

from backend.app.models.qc_report import QCReport, QCSeverity, QCStatus
from backend.app.models.reliability import ReliabilityAssessment, ReliabilityGrade


PRIMARY_METHOD_SUCCESS_STATUSES = {"completed", "completed_with_warning"}


def assess_reliability(
    qc_report: QCReport,
    validation_status: Optional[Dict[str, Any]] = None,
    plan_confirmed: bool = False,
    audit_artifacts_complete: bool = False,
    run_status: Optional[Dict[str, Any]] = None,
) -> ReliabilityAssessment:
    stop_conditions = [
        check.message
        for check in qc_report.checks
        if check.status == QCStatus.FAIL and check.severity == QCSeverity.ERROR
    ]
    downgrade_conditions: List[str] = []
    rationale: List[str] = []
    audit_notes: List[str] = []

    if stop_conditions:
        return ReliabilityAssessment(
            project_id=qc_report.project_id,
            grade=ReliabilityGrade.E,
            strong_conclusion_allowed=False,
            rationale=["Stop conditions are present."],
            stop_conditions=stop_conditions,
            downgrade_conditions=[],
            audit_notes=["Analysis should be blocked until stop conditions are resolved."],
        )

    if run_status is not None:
        return _assess_real_r_reliability(
            qc_report=qc_report,
            run_status=run_status,
            plan_confirmed=plan_confirmed,
            audit_artifacts_complete=audit_artifacts_complete,
        )

    for group, count in qc_report.group_counts.items():
        if count < 2:
            downgrade_conditions.append(f"Group '{group}' has fewer than 2 samples.")

    if qc_report.batch_group_assessment and qc_report.batch_group_assessment.is_potentially_confounding:
        downgrade_conditions.append("Batch and group appear potentially confounded.")

    warnings = [
        check.message
        for check in qc_report.checks
        if check.status == QCStatus.WARN or check.severity == QCSeverity.WARNING
    ]
    downgrade_conditions.extend(warnings)

    if not plan_confirmed:
        downgrade_conditions.append("Analysis plan has not been confirmed by the user.")

    validation_mode = (validation_status or {}).get("mode")
    concordant_methods = (validation_status or {}).get("concordant_methods", [])
    discordant_methods = (validation_status or {}).get("discordant_methods", [])

    if validation_mode in {None, "mock"}:
        downgrade_conditions.append("Validation is missing or mock-only.")
    if discordant_methods:
        downgrade_conditions.append(f"Validation methods disagree: {', '.join(discordant_methods)}.")
    if not audit_artifacts_complete:
        audit_notes.append("Audit artifacts are incomplete or have not been generated.")

    if downgrade_conditions:
        if any("fewer than 2 samples" in item or "confounded" in item for item in downgrade_conditions):
            grade = ReliabilityGrade.D
            rationale.append("Major design limitations reduce reliability.")
        else:
            grade = ReliabilityGrade.C
            rationale.append("QC passed, but validation or audit limitations make this exploratory.")
    elif len(concordant_methods) >= 2 and audit_artifacts_complete:
        grade = ReliabilityGrade.A
        rationale.append("QC passed and multiple validation methods are concordant.")
    elif len(concordant_methods) >= 1:
        grade = ReliabilityGrade.B
        rationale.append("QC passed and at least one validation method is concordant.")
    else:
        grade = ReliabilityGrade.C
        rationale.append("QC passed, but no validation concordance is available.")

    return ReliabilityAssessment(
        project_id=qc_report.project_id,
        grade=grade,
        strong_conclusion_allowed=grade in {ReliabilityGrade.A, ReliabilityGrade.B},
        rationale=rationale,
        stop_conditions=[],
        downgrade_conditions=downgrade_conditions,
        audit_notes=audit_notes,
    )


def _assess_real_r_reliability(
    qc_report: QCReport,
    run_status: Dict[str, Any],
    plan_confirmed: bool,
    audit_artifacts_complete: bool,
) -> ReliabilityAssessment:
    stop_conditions: List[str] = []
    downgrade_conditions: List[str] = []
    rationale: List[str] = []
    audit_notes: List[str] = []

    if not run_status:
        return _real_assessment(
            qc_report.project_id,
            ReliabilityGrade.E,
            ["run_status.json is missing."],
            ["Real runner status is unavailable."],
            [],
            ["Results are not reproducible without run_status.json."],
        )

    primary_status = run_status.get("primary_method_status")
    primary_completed_with_warning = primary_status == "completed_with_warning"
    if primary_status not in PRIMARY_METHOD_SUCCESS_STATUSES:
        stop_conditions.extend(run_status.get("errors") or [])
        if not stop_conditions:
            stop_conditions.append(f"DESeq2 primary method status is '{primary_status}'.")
        return _real_assessment(
            qc_report.project_id,
            ReliabilityGrade.E,
            stop_conditions,
            ["DESeq2 primary analysis did not complete."],
            [],
            ["No strong or exploratory biological conclusion should be generated."],
        )

    if primary_completed_with_warning:
        run_warnings = [
            str(warning)
            for warning in (run_status.get("warnings") or [])
            if warning
        ]
        if run_warnings:
            downgrade_conditions.extend(run_warnings)
        else:
            downgrade_conditions.append("DESeq2 completed with warning.")

    if not plan_confirmed:
        downgrade_conditions.append("Analysis plan has not been confirmed by the user.")

    serious_design_warning = _has_serious_design_warning(qc_report)
    if serious_design_warning:
        downgrade_conditions.append("QC has serious design warnings.")

    validation_method_status = run_status.get("validation_method_status") or {}
    completed_validation_methods = [
        method for method, status in validation_method_status.items() if status == "completed"
    ]
    skipped_or_failed_validation = [
        method for method, status in validation_method_status.items() if status in {"skipped", "failed"}
    ]
    score = _numeric_or_none(run_status.get("validation_consistency_score"))
    fdr_applied = bool(run_status.get("fdr_applied"))
    r_session_info_exists = _path_exists(run_status.get("r_session_info_path"))
    audit_log_exists = audit_artifacts_complete or _path_exists(run_status.get("audit_log_path"))

    if not fdr_applied:
        downgrade_conditions.append("FDR was not applied.")
    if not r_session_info_exists:
        audit_notes.append("r_session_info.txt is missing.")
    if not audit_log_exists:
        audit_notes.append("Audit log is missing.")

    if serious_design_warning:
        return _real_assessment(
            qc_report.project_id,
            ReliabilityGrade.D,
            [],
            ["DESeq2 completed, but serious QC or design warnings are present."],
            downgrade_conditions,
            audit_notes,
        )

    if not completed_validation_methods:
        downgrade_conditions.append("Validation methods were skipped or failed.")
        if skipped_or_failed_validation:
            downgrade_conditions.append(f"Validation not completed for: {', '.join(skipped_or_failed_validation)}.")
        return _real_assessment(
            qc_report.project_id,
            ReliabilityGrade.C,
            [],
            ["DESeq2 completed, but validation is unavailable; results are exploratory."],
            downgrade_conditions,
            audit_notes,
        )

    if score is None:
        downgrade_conditions.append("Validation consistency score is unavailable.")
        return _real_assessment(
            qc_report.project_id,
            ReliabilityGrade.C,
            [],
            ["DESeq2 completed, but validation consistency could not be evaluated."],
            downgrade_conditions,
            audit_notes,
        )

    if (
        not primary_completed_with_warning
        and score >= 0.8
        and fdr_applied
        and r_session_info_exists
        and audit_log_exists
    ):
        return _real_assessment(
            qc_report.project_id,
            ReliabilityGrade.A,
            [],
            ["QC passed, DESeq2 completed, validation is concordant, and audit artifacts are complete."],
            downgrade_conditions,
            audit_notes,
        )

    if score >= 0.6 and fdr_applied:
        return _real_assessment(
            qc_report.project_id,
            ReliabilityGrade.B,
            [],
            [
                "QC passed, DESeq2 completed, and at least one validation method is moderately concordant."
                if not primary_completed_with_warning
                else "DESeq2 completed with warning, and validation support is sufficient for grade B but not grade A."
            ],
            downgrade_conditions,
            audit_notes,
        )

    downgrade_conditions.append("Validation consistency is below the reliability threshold.")
    return _real_assessment(
        qc_report.project_id,
        ReliabilityGrade.C,
        [],
        ["DESeq2 completed, but validation support is insufficient; results are exploratory."],
        downgrade_conditions,
        audit_notes,
    )


def _real_assessment(
    project_id: str,
    grade: ReliabilityGrade,
    stop_conditions: List[str],
    rationale: List[str],
    downgrade_conditions: List[str],
    audit_notes: List[str],
) -> ReliabilityAssessment:
    return ReliabilityAssessment(
        project_id=project_id,
        grade=grade,
        strong_conclusion_allowed=grade in {ReliabilityGrade.A, ReliabilityGrade.B},
        rationale=rationale,
        stop_conditions=stop_conditions,
        downgrade_conditions=downgrade_conditions,
        audit_notes=audit_notes,
    )


def _has_serious_design_warning(qc_report: QCReport) -> bool:
    if qc_report.batch_group_assessment and qc_report.batch_group_assessment.is_potentially_confounding:
        return True
    for group_count in qc_report.group_counts.values():
        if group_count < 2:
            return True
    return any(
        check.status == QCStatus.WARN
        and check.name in {"batch_group_confounding", "group_sample_size"}
        for check in qc_report.checks
    )


def _numeric_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _path_exists(value: Any) -> bool:
    if not value:
        return False
    return Path(str(value)).exists()
