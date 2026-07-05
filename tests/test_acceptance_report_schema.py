from scripts.acceptance_phase_1 import (
    finalize_report_status,
    markdown_summary,
    new_acceptance_report,
    validate_acceptance_report_schema,
)


def test_acceptance_report_schema_has_required_fields() -> None:
    report = new_acceptance_report(
        base_url="http://127.0.0.1:8001",
        timestamp="20260705T000000Z",
        git_commit=None,
    )

    assert validate_acceptance_report_schema(report) == []
    assert report["pytest_summary"] == "not_run"
    assert report["overall_status"] == "not_run"


def test_acceptance_report_status_and_markdown_summary() -> None:
    report = new_acceptance_report(
        base_url="http://127.0.0.1:8001",
        timestamp="20260705T000000Z",
        git_commit="abc1234",
    )
    report["run_modes_tested"] = ["mock"]
    report["smoke_project_ids"]["mock"] = "proj_mock"
    report["final_statuses"]["mock"] = "completed"
    report["reliability_grades"]["mock"] = "C"

    finalize_report_status(report)
    markdown = markdown_summary(report)

    assert report["overall_status"] == "passed"
    assert "Phase 1 Acceptance Report" in markdown
    assert "proj_mock" in markdown
    assert "This acceptance report verifies workflow execution" in markdown

