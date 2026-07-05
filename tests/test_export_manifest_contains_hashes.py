import json
from pathlib import Path
from zipfile import ZipFile

from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


def test_export_manifest_contains_hashes_and_run_summary() -> None:
    fixture = setup_completed_with_warning_project()
    client = fixture["client"]
    project_id = fixture["project_id"]
    payload = client.post(f"/projects/{project_id}/export").json()

    with ZipFile(Path(payload["export_package_path"])) as archive:
        export_manifest = json.loads(archive.read("EXPORT_MANIFEST.json").decode("utf-8"))

    assert export_manifest["project_id"] == project_id
    assert export_manifest["manifest_present"] is True
    assert export_manifest["reliability_grade"] == "B"
    assert export_manifest["strong_conclusion_allowed"] is False
    assert export_manifest["primary_method_status"] == "completed_with_warning"
    assert export_manifest["validation_consistency_score"] == 1
    assert export_manifest["included_files"]
    assert all("path" in item for item in export_manifest["included_files"])
    assert all("sha256" in item for item in export_manifest["included_files"])
    assert all("size_bytes" in item for item in export_manifest["included_files"])
    assert any(item["path"] == "12_interpretation_summary.md" for item in export_manifest["included_files"])

