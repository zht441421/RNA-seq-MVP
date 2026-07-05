import json
from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.project import ProjectStatus
from backend.app.reports.evidence_package import create_evidence_package
from backend.app.services.artifact_service import STORE
from backend.app.services.qc_service import run_qc
from backend.app.services.reliability_service import assess_reliability
from tests.test_qc_rules import example_config


FALLBACK_WARNING = "DESeq2 standard dispersion fit failed; used gene-wise dispersion fallback."


def setup_completed_with_warning_project() -> Dict[str, Any]:
    project = STORE.create_project(
        name="completed with warning report fixture",
        description="Fixture for report hardening tests.",
        omics_type="bulk_rnaseq",
    )
    project_id = project.project_id
    config = example_config(project_id)
    qc_report = run_qc(config)
    plan = AnalysisPlan(project_id=project_id, design_formula="~ group", confirmed=True)
    artifact_root = Path("artifacts") / project_id
    env_dir = artifact_root / "09_environment"
    for directory in [
        artifact_root / "04_main_results",
        artifact_root / "05_validation_results",
        artifact_root / "07_tables",
        env_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    (artifact_root / "04_main_results" / "deseq2_results.csv").write_text("gene_id,log2FoldChange,padj\nGeneA,1.2,0.01\n", encoding="utf-8")
    (artifact_root / "05_validation_results" / "edger_results.csv").write_text("gene_id,logFC,FDR\nGeneA,1.1,0.02\n", encoding="utf-8")
    (artifact_root / "05_validation_results" / "limma_voom_results.csv").write_text("gene_id,logFC,adj.P.Val\nGeneA,1.3,0.03\n", encoding="utf-8")
    (artifact_root / "05_validation_results" / "validation_comparison.csv").write_text(
        "gene_id,edger_direction_consistent,limma_direction_consistent,significant_by_edger,significant_by_limma\nGeneA,true,true,true,true\n",
        encoding="utf-8",
    )
    (artifact_root / "07_tables" / "normalized_counts.csv").write_text("gene_id,S1,S2\nGeneA,10,12\n", encoding="utf-8")
    session_path = env_dir / "r_session_info.txt"
    session_path.write_text("R version 4.4.1\n", encoding="utf-8")
    runner_audit_path = env_dir / "docker_r_audit_log.json"
    runner_audit_path.write_text("{}", encoding="utf-8")
    run_status_path = env_dir / "run_status.json"
    run_status = {
        "execution_mode": "docker_r",
        "primary_method_status": "completed_with_warning",
        "validation_method_status": {"edgeR": "completed", "limma_voom": "completed"},
        "validation_consistency_score": 1,
        "validation_consistency_status": "computed",
        "fdr_applied": True,
        "warnings": [FALLBACK_WARNING],
        "errors": [],
        "r_session_info_path": str(session_path),
        "audit_log_path": str(runner_audit_path),
    }
    run_status_path.write_text(json.dumps(run_status), encoding="utf-8")

    reliability = assess_reliability(
        qc_report=qc_report,
        run_status=run_status,
        plan_confirmed=True,
        audit_artifacts_complete=True,
    )
    run_result = {
        "mode": "docker_r",
        "status": "completed",
        "run_status": run_status,
        "validation_status": {
            "mode": "docker_r",
            "completed_methods": ["edgeR", "limma_voom"],
            "validation_consistency_score": 1,
            "validation_consistency_status": "computed",
        },
        "docker_image": "bioinformatics-agent-r-bulk-rnaseq:0.1",
        "docker_available": True,
    }
    manifest = create_evidence_package(
        project_id,
        {
            "project": project,
            "config": config,
            "plan": plan,
            "qc_report": qc_report,
            "reliability": reliability,
            "run_result": run_result,
        },
    )

    STORE.analysis_configs[project_id] = config
    STORE.qc_reports[project_id] = qc_report
    STORE.plans[project_id] = plan
    STORE.reliability[project_id] = reliability
    STORE.results[project_id] = {
        "execution_mode": "docker_r",
        "primary_method": "DESeq2",
        "validation_methods": ["edgeR", "limma_voom"],
        "result_available": True,
        "message": "Dockerized R differential expression run completed.",
        "run_status": run_status,
        "evidence_manifest_path": str(Path(manifest["artifact_root"]) / "manifest.json"),
    }
    STORE.update_status(project_id, ProjectStatus.COMPLETED)
    return {"client": TestClient(app), "project_id": project_id, "manifest": manifest, "run_status": run_status}


def test_report_and_results_include_completed_with_warning_details() -> None:
    fixture = setup_completed_with_warning_project()
    client = fixture["client"]
    project_id = fixture["project_id"]

    report = client.get(f"/coze/projects/{project_id}/report").json()
    results = client.get(f"/projects/{project_id}/results").json()

    assert report["primary_method_status"] == "completed_with_warning"
    assert report["warnings"] == [FALLBACK_WARNING]
    assert report["errors"] == []
    assert report["validation_consistency_score"] == 1
    assert report["reliability_grade"] == "B"
    assert results["primary_method_status"] == "completed_with_warning"
    assert results["warnings"] == [FALLBACK_WARNING]
    assert results["validation_consistency_score"] == 1
