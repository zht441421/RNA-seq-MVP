from pathlib import Path
from zipfile import ZipFile

from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


def test_export_package_created_with_evidence_files() -> None:
    fixture = setup_completed_with_warning_project()
    client = fixture["client"]
    project_id = fixture["project_id"]

    response = client.post(f"/projects/{project_id}/export")
    assert response.status_code == 200
    payload = response.json()

    export_path = Path(payload["export_package_path"])
    assert payload["status"] == "created"
    assert export_path.exists()
    assert payload["export_package_sha256"]
    assert payload["size_bytes"] > 0
    assert payload["included_file_count"] > 0

    with ZipFile(export_path) as archive:
        names = set(archive.namelist())

    assert "EXPORT_MANIFEST.json" in names
    assert "manifest.json" in names
    assert "12_interpretation_summary.md" in names
    assert "08_reproducible_code/README_REPRODUCE.md" in names
    assert "08_reproducible_code/input_hashes.json" in names

