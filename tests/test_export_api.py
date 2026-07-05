from backend.app.services.artifact_service import STORE
from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


def test_export_api_get_create_and_coze_report_metadata() -> None:
    fixture = setup_completed_with_warning_project()
    client = fixture["client"]
    project_id = fixture["project_id"]
    result_before = STORE.results[project_id].copy()

    before = client.get(f"/projects/{project_id}/export")
    assert before.status_code == 200
    assert before.json()["status"] in {"not_created", "available"}

    created = client.post(f"/projects/{project_id}/export")
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["status"] == "created"

    after = client.get(f"/projects/{project_id}/export")
    assert after.status_code == 200
    assert after.json()["status"] == "available"
    assert after.json()["export_package_sha256"] == created_payload["export_package_sha256"]

    report = client.get(f"/coze/projects/{project_id}/report").json()
    assert report["export_metadata"]["status"] == "available"
    assert report["export_metadata"]["export_package_sha256"] == created_payload["export_package_sha256"]
    assert STORE.results[project_id] == result_before

