from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.reliability import ReliabilityAssessment, ReliabilityGrade
from backend.app.reports.evidence_package import create_evidence_package
from tests.evidence_helpers import default_config, manifest_entry
from tests.test_qc_rules import example_config
from backend.app.services.qc_service import run_qc


def test_manifest_marks_missing_and_not_applicable_artifacts() -> None:
    config = example_config("proj_manifest_missing")
    qc_report = run_qc(config)
    plan = AnalysisPlan(project_id=config.project_id, design_formula="~ group")
    reliability = ReliabilityAssessment(
        project_id=config.project_id,
        grade=ReliabilityGrade.E,
        strong_conclusion_allowed=False,
        rationale=["DESeq2 primary analysis did not complete."],
        stop_conditions=["Rscript executable was not found."],
    )
    run_result = {
        "mode": "real_r",
        "status": "failed",
        "run_status": {
            "primary_method_status": "failed",
            "validation_method_status": {"edgeR": "skipped", "limma_voom": "failed"},
            "fdr_applied": False,
        },
    }

    manifest = create_evidence_package(
        config.project_id,
        {
            "config": config,
            "plan": plan,
            "qc_report": qc_report,
            "reliability": reliability,
            "run_result": run_result,
        },
    )

    assert manifest_entry(manifest, "04_main_results/deseq2_results.csv")["status"] == "missing"
    assert manifest_entry(manifest, "05_validation_results/edger_results.csv")["status"] == "not_applicable"
    assert manifest_entry(manifest, "05_validation_results/limma_voom_results.csv")["status"] == "missing"

