from pathlib import Path


CORE_ENDPOINT_PATHS = (
    "/health",
    "/task/create",
    "/task/{task_id}/status",
    "/task/plan",
    "/task/qc",
    "/task/run",
    "/task/{task_id}/report",
    "/task/{task_id}/artifacts",
    "/task/{task_id}/audit",
    "/openapi.json",
)

KEY_TEST_FILES = (
    "tests/test_task_plan_endpoint.py",
    "tests/test_task_qc_endpoint.py",
    "tests/test_task_run_endpoint.py",
    "tests/test_task_report_endpoint.py",
    "tests/test_task_artifacts_endpoint.py",
    "tests/test_task_audit_endpoint.py",
    "tests/test_task_lifecycle_placeholder_contract.py",
    "tests/test_task_error_contract.py",
    "tests/test_openapi_contract.py",
)


def test_phase_2_completion_baseline_doc_exists_and_defines_contract() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    doc_path = repo_root / "docs" / "phase-2-completion-baseline.md"

    assert doc_path.exists()
    text = doc_path.read_text(encoding="utf-8")
    lower_text = text.lower()

    for endpoint_path in CORE_ENDPOINT_PATHS:
        assert endpoint_path in text

    assert "no real rna-seq execution yet" in lower_text
    assert "no database persistence yet" in lower_text
    assert "no durable audit log yet" in lower_text
    assert "phase 3 recommended direction" in lower_text
    assert "openapi schema" in lower_text
    assert "docs/openapi.json" in lower_text
    assert "scripts/export_openapi_schema.py" in lower_text
    assert "python -m pytest" in lower_text

    for test_file in KEY_TEST_FILES:
        assert test_file in text
