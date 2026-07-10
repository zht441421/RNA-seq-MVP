from pathlib import Path


RUNBOOK_PATH = Path("docs/phase-6-4-deployment-runbook.md")
CHECKLIST_PATH = Path("docs/phase-6-4-operator-checklist.md")
README_PATH = Path("README.md")


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_phase_6_4_deployment_docs_exist() -> None:
    assert RUNBOOK_PATH.is_file()
    assert CHECKLIST_PATH.is_file()


def test_readme_mentions_phase_6_4() -> None:
    assert README_PATH.is_file()
    lowered = _normalized(README_PATH)

    assert "phase 6.4" in lowered
    assert "docs/phase-6-4-deployment-runbook.md" in lowered
    assert "docs/phase-6-4-operator-checklist.md" in lowered


def test_phase_6_4_runbook_mentions_required_operational_topics() -> None:
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    lowered = _normalized(RUNBOOK_PATH)

    for environment_variable in (
        "BIOINFO_INPUT_ROOT",
        "BIOINFO_OUTPUT_ROOT",
        "BIOINFO_TASK_STORE_PATH",
    ):
        assert environment_variable in text

    for required_text in (
        "deployment runbook",
        "uvicorn",
        "get /health",
        "local smoke test",
        "coze base url",
        "reverse proxy",
        "sqlite",
        "artifact download",
        "coze-summary",
        "deseq2 preflight",
        "no real coze api publication yet",
        "no frontend",
        "no edger",
        "no limma",
        "no enrichment",
        "no arbitrary filesystem reads",
        "no local absolute paths",
        "no traceback/token/password/secret leakage",
        "relative download urls only",
    ):
        assert required_text in lowered


def test_phase_6_4_runbook_documents_launch_and_validation_commands() -> None:
    lowered = _normalized(RUNBOOK_PATH)

    for required_text in (
        "uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload",
        "python -m uvicorn backend.app.main:app --host 127.0.0.1 "
        "--port 8000 --workers 1",
        "python scripts/run_phase_6_3_local_api_smoke_test.py",
        "python scripts/validate_phase_6_2_coze_manifest.py",
        "data/inputs",
        "data/outputs",
        "data/state",
    ):
        assert required_text in lowered


def test_phase_6_4_runbook_documents_required_failure_modes_and_rollback() -> None:
    lowered = _normalized(RUNBOOK_PATH)

    for required_text in (
        "service not starting",
        "port already in use",
        "missing input files",
        "invalid contrast",
        "artifact not found",
        "deseq2 preflight reports not ready",
        "unsafe path rejected",
        "git tag",
        "restart the service",
        "restore sqlite state and output artifacts",
    ):
        assert required_text in lowered
