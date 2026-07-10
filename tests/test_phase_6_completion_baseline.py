from pathlib import Path


BASELINE_PATH = Path("docs/phase-6-completion-baseline.md")
CHECKLIST_PATH = Path("docs/phase-6-deployment-readiness-checklist.md")
README_PATH = Path("README.md")


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_phase_6_completion_baseline_docs_exist() -> None:
    assert BASELINE_PATH.is_file()
    assert CHECKLIST_PATH.is_file()


def test_readme_mentions_phase_6_deployment_readiness_baseline() -> None:
    assert README_PATH.is_file()
    lowered = _normalized(README_PATH)

    assert "phase 6 deployment-readiness baseline" in lowered
    assert "docs/phase-6-completion-baseline.md" in lowered
    assert "docs/phase-6-deployment-readiness-checklist.md" in lowered


def test_phase_6_completion_baseline_mentions_all_milestones() -> None:
    lowered = _normalized(BASELINE_PATH)

    for milestone in (
        "coze api deployment contract",
        "coze plugin / openapi manifest preparation",
        "local api smoke test",
        "deployment runbook",
        "operator checklist",
    ):
        assert milestone in lowered


def test_phase_6_completion_baseline_mentions_required_status_and_materials() -> None:
    text = BASELINE_PATH.read_text(encoding="utf-8")
    lowered = _normalized(BASELINE_PATH)

    for environment_variable in (
        "BIOINFO_INPUT_ROOT",
        "BIOINFO_OUTPUT_ROOT",
        "BIOINFO_TASK_STORE_PATH",
        "BIOINFO_SMOKE_TEST_PORT",
    ):
        assert environment_variable in text

    for required_text in (
        "local launch verification",
        "coze/api integration readiness",
        "operator checklist",
        "current environment variables",
        "local smoke test",
        "openapi subset",
        "example payloads",
        "safety boundaries",
        "known limitations",
        "baseline tag plan",
        "phase-6-5-completion-baseline",
        "phase-6-deployment-readiness-baseline",
    ):
        assert required_text in lowered


def test_phase_6_deployment_readiness_checklist_mentions_required_topics() -> None:
    lowered = _normalized(CHECKLIST_PATH)

    for required_text in (
        "openapi",
        "coze openapi subset",
        "example payloads",
        "health check",
        "artifact download",
        "coze-summary",
        "input registration",
        "explicit contrast",
        "deseq2 preflight",
        "release tags",
        "future phase 7",
    ):
        assert required_text in lowered
