from pathlib import Path

from backend.app.services.artifact_service import STORE
from backend.app.services.result_interpretation import build_result_interpretation
from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


def test_result_interpretation_summary_counts_and_top_candidate_signals() -> None:
    fixture = setup_completed_with_warning_project()
    project_id = fixture["project_id"]
    interpretation = build_result_interpretation(
        project_id=project_id,
        reliability=STORE.reliability[project_id],
        result_summary=STORE.results[project_id],
        artifact_root=Path("artifacts") / project_id,
    )

    assert interpretation["interpretation_allowed"] is True
    assert interpretation["strong_conclusion_allowed"] is False
    assert interpretation["reliability_grade"] == "B"
    assert interpretation["primary_method_status"] == "completed_with_warning"
    assert interpretation["summary"]["deseq2_total_genes"] == 1
    assert interpretation["summary"]["deseq2_significant_genes"] == 1
    assert interpretation["summary"]["upregulated_genes"] == 1
    assert interpretation["summary"]["downregulated_genes"] == 0
    assert interpretation["summary"]["validation_consistency_score"] == 1
    assert interpretation["top_genes_label"] == "Top candidate statistical signals"
    assert interpretation["top_genes"][0]["interpretation_label"] == "candidate statistical signal"
    assert interpretation["top_genes"][0]["method_support"] == ["DESeq2", "edgeR", "limma_voom"]

