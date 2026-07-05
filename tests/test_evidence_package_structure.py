from tests.evidence_helpers import manifest_entry, run_api_project


def test_mock_run_generates_complete_evidence_package_structure() -> None:
    result = run_api_project(run_mode="mock")
    artifact_root = result["artifact_root"]
    manifest = result["manifest"]

    assert (artifact_root / "01_summary.md").exists()
    assert (artifact_root / "02_qc_report.md").exists()
    assert (artifact_root / "03_method_selection.md").exists()
    assert (artifact_root / "10_audit_log.json").exists()
    assert (artifact_root / "11_reliability_report.md").exists()
    assert (artifact_root / "manifest.json").exists()
    for directory in [
        "04_main_results",
        "05_validation_results",
        "06_figures",
        "07_tables",
        "08_reproducible_code",
        "09_environment",
    ]:
        assert (artifact_root / directory).is_dir()
        assert manifest_entry(manifest, f"{directory}/")["status"] == "present"

    assert manifest_entry(manifest, "01_summary.md")["status"] == "present"
    assert manifest_entry(manifest, "04_main_results/deseq2_results.csv")["status"] == "not_applicable"

