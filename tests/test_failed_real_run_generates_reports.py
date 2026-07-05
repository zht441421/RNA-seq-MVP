from tests.evidence_helpers import manifest_entry, run_api_project


def test_failed_real_run_generates_reports_audit_and_manifest() -> None:
    result = run_api_project(
        run_mode="real_r",
        rscript_executable="definitely_missing_Rscript_for_failed_evidence_test",
    )
    manifest = result["manifest"]
    artifact_root = result["artifact_root"]
    run = result["run"]

    assert run["status"] == "failed"
    assert run["reliability"]["grade"] == "E"
    for relative_path in [
        "01_summary.md",
        "02_qc_report.md",
        "03_method_selection.md",
        "10_audit_log.json",
        "11_reliability_report.md",
        "manifest.json",
    ]:
        assert (artifact_root / relative_path).exists()
        assert manifest_entry(manifest, relative_path)["status"] == "present"

    summary = (artifact_root / "01_summary.md").read_text(encoding="utf-8")
    reliability_report = (artifact_root / "11_reliability_report.md").read_text(encoding="utf-8")
    assert "Current evidence is not sufficient for a strong scientific conclusion." in summary
    assert "No scientific conclusion should be generated from this run." in reliability_report
