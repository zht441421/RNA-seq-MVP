from pathlib import Path


DOC_PATH = Path("docs/phase-6-3-local-api-smoke-test.md")
README_PATH = Path("README.md")


def test_phase_6_3_local_api_smoke_test_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_readme_mentions_phase_6_3() -> None:
    assert README_PATH.is_file()
    assert "phase 6.3" in README_PATH.read_text(encoding="utf-8").lower()


def test_phase_6_3_local_api_smoke_test_doc_mentions_required_topics() -> None:
    lowered = DOC_PATH.read_text(encoding="utf-8").lower()

    for required_text in (
        "local api smoke test",
        "get /health",
        "post /task/create",
        "post /task/{task_id}/inputs/register",
        "post /task/run",
        "get /task/{task_id}/coze-summary",
        "artifact download",
        "minimal_cpm_log2fc",
        "explicit contrast",
        "no real coze api call",
        "no public deployment",
        "local-only safety boundary",
    ):
        assert required_text in lowered

    assert "uvicorn" in lowered or "local server" in lowered
