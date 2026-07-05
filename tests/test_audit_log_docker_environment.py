import json

from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.reliability import ReliabilityAssessment, ReliabilityGrade
from backend.app.reports.evidence_package import create_evidence_package
from backend.app.services.qc_service import run_qc
from tests.test_qc_rules import example_config


def test_audit_log_records_docker_environment(tmp_path) -> None:
    config = example_config("proj_docker_audit")
    qc_report = run_qc(config)
    plan = AnalysisPlan(project_id=config.project_id, design_formula="~ batch + age + group")
    reliability = ReliabilityAssessment(
        project_id=config.project_id,
        grade=ReliabilityGrade.E,
        strong_conclusion_allowed=False,
        rationale=["DESeq2 primary analysis did not complete."],
        stop_conditions=["Docker image is not available."],
    )
    run_result = {
        "mode": "docker_r",
        "status": "failed",
        "docker_image": "bioinformatics-agent-r-bulk-rnaseq:0.1",
        "docker_available": True,
        "run_status": {
            "primary_method_status": "failed",
            "validation_method_status": {},
            "fdr_applied": False,
            "docker_image": "bioinformatics-agent-r-bulk-rnaseq:0.1",
            "docker_available": True,
            "package_status": {
                "DESeq2": {"installed": True, "version": "1.44.0"},
            },
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
    audit_path = tmp_path / "unused"
    audit = json.loads((__import__("pathlib").Path(manifest["artifact_root"]) / "10_audit_log.json").read_text(encoding="utf-8"))

    assert audit["environment"]["run_mode"] == "docker_r"
    assert audit["environment"]["docker_image"] == "bioinformatics-agent-r-bulk-rnaseq:0.1"
    assert audit["environment"]["docker_available"] is True
    assert audit["environment"]["package_versions"]["DESeq2"] == "1.44.0"
