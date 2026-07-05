from pathlib import Path

from backend.app.models.reliability import ReliabilityGrade
from backend.app.services.reliability_service import assess_reliability
from tests.test_reliability_real_run import qc_report, run_status


def test_docker_r_reliability_grade_a_uses_real_run_rules(tmp_path: Path) -> None:
    status = run_status(tmp_path, 0.9)
    status["execution_mode"] = "docker_r"
    status["docker_image"] = "bioinformatics-agent-r-bulk-rnaseq:0.1"

    assessment = assess_reliability(
        qc_report=qc_report("proj_docker_rel_a"),
        run_status=status,
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.A
    assert assessment.strong_conclusion_allowed is True


def test_docker_r_reliability_grade_e_when_deseq2_failed() -> None:
    status = {
        "execution_mode": "docker_r",
        "primary_method_status": "failed",
        "validation_method_status": {},
        "validation_consistency_score": None,
        "validation_consistency_status": "docker_image_unavailable",
        "fdr_applied": False,
        "errors": ["Docker image is not available."],
    }

    assessment = assess_reliability(
        qc_report=qc_report("proj_docker_rel_e"),
        run_status=status,
        plan_confirmed=True,
        audit_artifacts_complete=False,
    )

    assert assessment.grade == ReliabilityGrade.E
    assert assessment.strong_conclusion_allowed is False
    assert assessment.stop_conditions

