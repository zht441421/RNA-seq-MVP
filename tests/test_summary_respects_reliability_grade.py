from tests.evidence_helpers import run_api_project


def test_grade_c_summary_disallows_strong_scientific_conclusion() -> None:
    result = run_api_project(run_mode="mock")
    summary = (result["artifact_root"] / "01_summary.md").read_text(encoding="utf-8")

    assert "Reliability grade: C" in summary
    assert "Allowed conclusion level: Exploratory findings only." in summary
    assert "Current evidence is not sufficient for a strong scientific conclusion." in summary
    assert "permits relatively strong statistical conclusions" not in summary

