from pathlib import Path


def test_phase_5_completion_baseline_docs_exist_and_freeze_scope() -> None:
    baseline_path = Path("docs/phase-5-completion-baseline.md")
    checklist_path = Path("docs/phase-5-mvp-integration-checklist.md")
    readme_path = Path("README.md")

    assert baseline_path.is_file()
    assert checklist_path.is_file()
    assert readme_path.is_file()

    baseline_text = baseline_path.read_text(encoding="utf-8").lower()
    checklist_text = checklist_path.read_text(encoding="utf-8").lower()
    readme_text = readme_path.read_text(encoding="utf-8").lower()

    assert "current phase 5 mvp integration status" in readme_text

    for milestone in (
        "persistent task storage",
        "artifact download",
        "coze summary",
        "task input registration",
        "contrast/reference control",
        "coze-ready demo",
    ):
        assert milestone in baseline_text

    for endpoint in (
        "post /task/create",
        "post /task/{task_id}/inputs/register",
        "post /task/run",
        "get /task/{task_id}/artifacts",
        "get /task/{task_id}/artifacts/{artifact_name}/download",
        "get /task/{task_id}/coze-summary",
    ):
        assert endpoint in baseline_text

    for safety_boundary in (
        "no absolute paths",
        "no arbitrary filesystem reads",
        "no traceback/token/password/secret leakage",
    ):
        assert safety_boundary in baseline_text

    for limitation in (
        "no frontend",
        "no real coze api call",
        "no edger",
        "no limma",
        "no enrichment",
        "deseq2 requires r/rscript/deseq2",
    ):
        assert limitation in baseline_text

    for checklist_item in (
        "openapi",
        "demo script",
        "tests",
        "tags",
    ):
        assert checklist_item in checklist_text
