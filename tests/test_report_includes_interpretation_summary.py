from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


def test_results_and_coze_report_include_interpretation_summary() -> None:
    fixture = setup_completed_with_warning_project()
    client = fixture["client"]
    project_id = fixture["project_id"]

    results = client.get(f"/projects/{project_id}/results").json()
    report = client.get(f"/coze/projects/{project_id}/report").json()

    for payload in [results, report]:
        assert payload["interpretation_summary"]["primary_method_status"] == "completed_with_warning"
        assert payload["interpretation_summary"]["strong_conclusion_allowed"] is False
        assert payload["top_genes"][0]["interpretation_label"] == "candidate statistical signal"
        assert "主分析已完成，但存在方法学 warning，请谨慎解释结果。" in payload["interpretation_guardrails"]
        assert payload["artifact_presence_summary"]["12_interpretation_summary.md"] == "present"

