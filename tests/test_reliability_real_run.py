from pathlib import Path

from backend.app.models.qc_report import QCCheck, QCReport, QCSeverity, QCStatus
from backend.app.models.reliability import ReliabilityGrade
from backend.app.services.reliability_service import assess_reliability


def qc_report(project_id: str = "proj_real_reliability", group_counts: dict[str, int] = None) -> QCReport:
    return QCReport(
        project_id=project_id,
        passed=True,
        checks=[],
        group_counts=group_counts or {"control": 3, "treatment": 3},
    )


def run_status(tmp_path: Path, score: float | None, validation_status: dict[str, str] = None) -> dict:
    session_info = tmp_path / "r_session_info.txt"
    audit_log = tmp_path / "audit_log.json"
    session_info.write_text("R session info", encoding="utf-8")
    audit_log.write_text("{}", encoding="utf-8")
    return {
        "execution_mode": "real_r",
        "primary_method_status": "completed",
        "validation_method_status": validation_status or {"edgeR": "completed", "limma_voom": "completed"},
        "validation_consistency_score": score,
        "validation_consistency_status": "computed" if score is not None else "no_validation_comparisons",
        "fdr_applied": True,
        "r_session_info_path": str(session_info),
        "audit_log_path": str(audit_log),
    }


def test_real_run_reliability_grade_a(tmp_path: Path) -> None:
    assessment = assess_reliability(
        qc_report=qc_report(),
        run_status=run_status(tmp_path, 0.9),
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.A
    assert assessment.strong_conclusion_allowed is True


def test_real_run_reliability_grade_b(tmp_path: Path) -> None:
    assessment = assess_reliability(
        qc_report=qc_report(),
        run_status=run_status(tmp_path, 0.65, {"edgeR": "completed", "limma_voom": "failed"}),
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.B
    assert assessment.strong_conclusion_allowed is True


def test_real_run_reliability_grade_c_for_missing_validation(tmp_path: Path) -> None:
    assessment = assess_reliability(
        qc_report=qc_report(),
        run_status=run_status(tmp_path, None, {"edgeR": "skipped", "limma_voom": "failed"}),
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.C
    assert assessment.strong_conclusion_allowed is False


def test_real_run_reliability_grade_d_for_serious_qc_warning(tmp_path: Path) -> None:
    report = qc_report(group_counts={"control": 1, "treatment": 3})
    report.checks.append(
        QCCheck(
            name="group_sample_size",
            status=QCStatus.WARN,
            severity=QCSeverity.WARNING,
            message="Group control has fewer than 2 samples.",
        )
    )
    assessment = assess_reliability(
        qc_report=report,
        run_status=run_status(tmp_path, 0.95),
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.D
    assert assessment.strong_conclusion_allowed is False


def test_real_run_reliability_grade_e_for_failed_primary(tmp_path: Path) -> None:
    status = run_status(tmp_path, None)
    status["primary_method_status"] = "failed"
    status["errors"] = ["DESeq2 is not installed."]

    assessment = assess_reliability(
        qc_report=qc_report(),
        run_status=status,
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.E
    assert assessment.strong_conclusion_allowed is False
    assert assessment.stop_conditions


def test_real_run_reliability_grade_e_for_unavailable_r_environment() -> None:
    status = {
        "execution_mode": "real_r",
        "primary_method_status": "failed",
        "validation_method_status": {},
        "validation_consistency_score": None,
        "validation_consistency_status": "rscript_unavailable",
        "fdr_applied": False,
        "errors": ["Rscript executable was not found."],
    }

    assessment = assess_reliability(
        qc_report=qc_report(),
        run_status=status,
        plan_confirmed=True,
        audit_artifacts_complete=False,
    )

    assert assessment.grade == ReliabilityGrade.E
    assert assessment.strong_conclusion_allowed is False
    assert "Rscript executable was not found." in assessment.stop_conditions
