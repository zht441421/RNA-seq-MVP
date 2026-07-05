from tests.evidence_helpers import manifest_entry
from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


def test_artifacts_endpoint_returns_manifest_with_key_artifact_statuses() -> None:
    fixture = setup_completed_with_warning_project()
    client = fixture["client"]
    project_id = fixture["project_id"]

    manifest = client.get(f"/projects/{project_id}/artifacts").json()
    results = client.get(f"/projects/{project_id}/results").json()

    assert manifest["project_id"] == project_id
    assert "files" in manifest
    assert manifest_entry(manifest, "04_main_results/deseq2_results.csv")["status"] == "present"
    assert manifest_entry(manifest, "05_validation_results/edger_results.csv")["status"] == "present"
    assert manifest_entry(manifest, "05_validation_results/limma_voom_results.csv")["status"] == "present"
    assert manifest_entry(manifest, "05_validation_results/validation_comparison.csv")["status"] == "present"
    assert manifest_entry(manifest, "09_environment/run_status.json")["status"] == "present"
    assert manifest_entry(manifest, "09_environment/r_session_info.txt")["status"] == "present"
    assert manifest_entry(manifest, "10_audit_log.json")["status"] == "present"
    assert manifest_entry(manifest, "11_reliability_report.md")["status"] == "present"
    assert manifest_entry(manifest, "12_interpretation_summary.md")["status"] == "present"
    assert manifest_entry(manifest, "manifest.json")["status"] == "present"
    assert results["artifact_presence_summary"]["04_main_results/deseq2_results.csv"] == "present"
    assert results["artifact_presence_summary"]["05_validation_results/validation_comparison.csv"] == "present"
    assert results["artifact_presence_summary"]["12_interpretation_summary.md"] == "present"
