import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


DEMO_METADATA_FILE = "rnaseq_minimal/metadata.csv"
DEMO_COUNT_MATRIX_FILE = "rnaseq_minimal/counts.csv"
FORBIDDEN_PUBLIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "traceback",
    "token",
    "password",
    "secret",
)


@pytest.fixture()
def isolated_demo_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(Path("data/demo").resolve()))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "state" / "tasks.sqlite3"))
    reset_registry()
    yield output_root
    reset_registry()


def _assert_safe(value: object) -> None:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    lowered = text.lower()
    for forbidden_fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert forbidden_fragment not in lowered


def _create_task(client: TestClient) -> str:
    response = client.post("/task/create", json={})
    assert response.status_code == 200
    return response.json()["task_id"]


def _plan_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "phase_5_6_contract_demo",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _qc_payload(task_id: str) -> dict[str, object]:
    return {
        **_plan_payload(task_id),
        "metadata_file": DEMO_METADATA_FILE,
        "count_matrix_file": DEMO_COUNT_MATRIX_FILE,
        "sample_id_column": "sample_id",
    }


def _run_payload(task_id: str) -> dict[str, object]:
    return {
        **_plan_payload(task_id),
        "execution_mode": "minimal_real",
        "analysis_method": "minimal_cpm_log2fc",
        "contrast_column": "condition",
        "contrast_numerator": "treatment",
        "contrast_denominator": "control",
    }


def test_phase_5_6_registered_input_lifecycle_is_coze_ready(
    isolated_demo_env: Path,
) -> None:
    client = TestClient(app)
    task_id = _create_task(client)

    metadata_register = client.post(
        f"/task/{task_id}/inputs/register",
        json={
            "input_role": "metadata",
            "source_relative_path": DEMO_METADATA_FILE,
        },
    )
    count_register = client.post(
        f"/task/{task_id}/inputs/register",
        json={
            "input_role": "count_matrix",
            "source_relative_path": DEMO_COUNT_MATRIX_FILE,
        },
    )
    assert metadata_register.status_code == 200
    assert count_register.status_code == 200

    plan_response = client.post("/task/plan", json=_plan_payload(task_id))
    qc_response = client.post("/task/qc", json=_qc_payload(task_id))
    assert plan_response.status_code == 200
    assert qc_response.status_code == 200

    run_response = client.post("/task/run", json=_run_payload(task_id))
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["status"] == "minimal_analysis_completed"

    execution_summary = json.loads(
        (isolated_demo_env / "tasks" / task_id / "execution_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert execution_summary["contrast"]["direction"] == "treatment_vs_control"
    assert execution_summary["positive_log2fc_interpretation"] == (
        "Higher in treatment relative to control"
    )
    assert execution_summary["negative_log2fc_interpretation"] == (
        "Lower in treatment relative to control"
    )

    artifacts_response = client.get(f"/task/{task_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifacts_body = artifacts_response.json()
    artifact_names = [artifact["name"] for artifact in artifacts_body["artifacts"]]
    assert "report.md" in artifact_names
    assert "differential_expression_results.csv" in artifact_names
    assert all(not str(artifact["path"]).startswith(("file://", "http://", "https://")) for artifact in artifacts_body["artifacts"])

    report_download = client.get(f"/task/{task_id}/artifacts/report.md/download")
    csv_download = client.get(
        f"/task/{task_id}/artifacts/differential_expression_results.csv/download"
    )
    assert report_download.status_code == 200
    assert csv_download.status_code == 200
    assert "Contrast direction" in report_download.text
    assert "treatment_vs_control" in report_download.text
    assert "contrast_direction" in csv_download.text

    coze_response = client.get(f"/task/{task_id}/coze-summary")
    assert coze_response.status_code == 200
    coze_summary = coze_response.json()
    for field in (
        "summary_message",
        "result_files",
        "download_links",
        "contrast",
        "positive_log2fc_interpretation",
        "negative_log2fc_interpretation",
        "warnings",
        "limitations",
        "safe_to_present",
    ):
        assert field in coze_summary

    assert coze_summary["safe_to_present"] is True
    assert coze_summary["contrast"]["direction"] == "treatment_vs_control"
    assert coze_summary["positive_log2fc_interpretation"] == (
        "Higher in treatment relative to control"
    )
    assert coze_summary["negative_log2fc_interpretation"] == (
        "Lower in treatment relative to control"
    )
    assert coze_summary["registered_inputs"] == {
        "count_matrix": DEMO_COUNT_MATRIX_FILE,
        "metadata": DEMO_METADATA_FILE,
    }
    for artifact_name, download_url in coze_summary["download_links"].items():
        assert download_url.startswith(f"/task/{task_id}/artifacts/")
        assert download_url.endswith("/download")
        assert not download_url.startswith(("file://", "http://", "https://"))

    for public_payload in (
        metadata_register.json(),
        count_register.json(),
        plan_response.json(),
        qc_response.json(),
        run_body,
        artifacts_body,
        coze_summary,
        report_download.text,
        csv_download.text,
    ):
        _assert_safe(public_payload)
