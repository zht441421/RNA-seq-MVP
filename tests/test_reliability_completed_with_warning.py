from pathlib import Path

from backend.app.models.reliability import ReliabilityGrade
from backend.app.services.reliability_service import assess_reliability
from tests.test_reliability_real_run import qc_report, run_status


def test_completed_with_warning_cannot_receive_grade_a(tmp_path: Path) -> None:
    status = run_status(tmp_path, 0.95)
    status["primary_method_status"] = "completed_with_warning"
    status["warnings"] = [
        "DESeq2 standard dispersion fit failed; used gene-wise dispersion fallback.",
    ]

    assessment = assess_reliability(
        qc_report=qc_report("proj_warning_b"),
        run_status=status,
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.B
    assert assessment.strong_conclusion_allowed is True
    assert any("dispersion fallback" in condition for condition in assessment.downgrade_conditions)


def test_completed_with_warning_without_validation_is_grade_c(tmp_path: Path) -> None:
    status = run_status(tmp_path, None, {"edgeR": "skipped", "limma_voom": "failed"})
    status["primary_method_status"] = "completed_with_warning"
    status["warnings"] = [
        "DESeq2 standard dispersion fit failed; used gene-wise dispersion fallback.",
    ]

    assessment = assess_reliability(
        qc_report=qc_report("proj_warning_c"),
        run_status=status,
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.C
    assert assessment.strong_conclusion_allowed is False
