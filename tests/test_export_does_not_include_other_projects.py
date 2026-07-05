from pathlib import Path
from zipfile import ZipFile

from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


def test_export_does_not_include_other_project_artifacts() -> None:
    first = setup_completed_with_warning_project()
    second = setup_completed_with_warning_project()
    client = first["client"]
    first_project_id = first["project_id"]
    second_project_id = second["project_id"]

    payload = client.post(f"/projects/{first_project_id}/export").json()
    with ZipFile(Path(payload["export_package_path"])) as archive:
        names = archive.namelist()
        export_manifest_text = archive.read("EXPORT_MANIFEST.json").decode("utf-8")

    assert not any(second_project_id in name for name in names)
    assert second_project_id not in export_manifest_text
    assert not any(name.startswith("../") for name in names)
    assert not any("__pycache__" in name for name in names)
    assert not any(name.endswith(".pyc") for name in names)
