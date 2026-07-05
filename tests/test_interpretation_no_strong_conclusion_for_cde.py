import pytest

from backend.app.models.reliability import ReliabilityAssessment, ReliabilityGrade
from backend.app.services.result_interpretation import STRONG_CONCLUSION_WARNING, build_result_interpretation


@pytest.mark.parametrize("grade", [ReliabilityGrade.C, ReliabilityGrade.D])
def test_c_or_d_interpretation_requires_strong_conclusion_warning(tmp_path, grade: ReliabilityGrade) -> None:
    reliability = ReliabilityAssessment(
        project_id=f"proj_{grade.value.lower()}",
        grade=grade,
        strong_conclusion_allowed=False,
    )
    interpretation = build_result_interpretation(
        project_id=reliability.project_id,
        reliability=reliability,
        result_summary={"status": "completed", "run_status": {"primary_method_status": "completed"}},
        artifact_root=tmp_path,
    )

    assert interpretation["interpretation_allowed"] is True
    assert interpretation["strong_conclusion_allowed"] is False
    assert STRONG_CONCLUSION_WARNING in interpretation["guardrails"]


def test_failed_or_grade_e_run_does_not_emit_top_genes(tmp_path) -> None:
    reliability = ReliabilityAssessment(
        project_id="proj_e",
        grade=ReliabilityGrade.E,
        strong_conclusion_allowed=False,
    )
    interpretation = build_result_interpretation(
        project_id="proj_e",
        reliability=reliability,
        result_summary={
            "status": "failed",
            "run_status": {"primary_method_status": "failed", "errors": ["DESeq2 failed."]},
        },
        artifact_root=tmp_path,
    )

    assert interpretation["interpretation_allowed"] is False
    assert interpretation["strong_conclusion_allowed"] is False
    assert interpretation["top_genes"] == []
    assert STRONG_CONCLUSION_WARNING in interpretation["guardrails"]
    assert "DESeq2 failed." in interpretation["failure_reason"]

