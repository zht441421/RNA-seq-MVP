from backend.app.models.qc_report import QCCheck, QCReport, QCSeverity, QCStatus
from backend.app.models.reliability import ReliabilityGrade
from backend.app.services.reliability_service import assess_reliability
from tests.test_qc_rules import example_config
from backend.app.services.qc_service import run_qc


def test_mock_validation_yields_exploratory_grade_c() -> None:
    qc_report = run_qc(example_config("proj_reliability_c"))
    assessment = assess_reliability(
        qc_report=qc_report,
        validation_status={"mode": "mock", "concordant_methods": [], "discordant_methods": []},
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.C
    assert assessment.strong_conclusion_allowed is False


def test_stop_condition_yields_grade_e() -> None:
    qc_report = QCReport(
        project_id="proj_reliability_e",
        passed=False,
        checks=[
            QCCheck(
                name="sample_ids_aligned",
                status=QCStatus.FAIL,
                severity=QCSeverity.ERROR,
                message="Sample IDs do not align.",
            )
        ],
    )
    assessment = assess_reliability(qc_report=qc_report, plan_confirmed=True, audit_artifacts_complete=True)

    assert assessment.grade == ReliabilityGrade.E
    assert assessment.strong_conclusion_allowed is False
    assert assessment.stop_conditions


def test_low_sample_size_yields_grade_d() -> None:
    qc_report = QCReport(
        project_id="proj_reliability_d",
        passed=True,
        checks=[],
        group_counts={"control": 1, "treatment": 1},
    )
    assessment = assess_reliability(
        qc_report=qc_report,
        validation_status={"mode": "real", "concordant_methods": ["edgeR"], "discordant_methods": []},
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )

    assert assessment.grade == ReliabilityGrade.D
    assert assessment.strong_conclusion_allowed is False

