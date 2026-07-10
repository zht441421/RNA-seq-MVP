from pathlib import Path


BASELINE_PATH = Path("docs/phase-7-1-api-security-baseline.md")
CHECKLIST_PATH = Path("docs/phase-7-1-production-hardening-checklist.md")
README_PATH = Path("README.md")


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_phase_7_1_security_docs_exist() -> None:
    assert BASELINE_PATH.is_file()
    assert CHECKLIST_PATH.is_file()


def test_readme_mentions_phase_7_1() -> None:
    lowered = _normalized(README_PATH)
    assert "phase 7.1 production-facing hardening / api security baseline" in lowered
    assert "docs/phase-7-1-api-security-baseline.md" in lowered
    assert "docs/phase-7-1-production-hardening-checklist.md" in lowered


def test_security_baseline_mentions_required_topics() -> None:
    lowered = _normalized(BASELINE_PATH)
    for required_text in (
        "production-facing hardening",
        "phase 6 deployment-readiness baseline",
        "api key",
        "x-bioinfo-api-key",
        "reverse proxy",
        "cors",
        "request size limits",
        "timeout limits",
        "no arbitrary filesystem reads",
        "no local absolute paths",
        "relative download urls",
        "no traceback/token/password/secret leakage",
        "artifact download safety",
        "sqlite",
        "logging",
        "deseq2 subprocess",
        "rate limiting",
        "known limitations",
        "future phase 7",
    ):
        assert required_text in lowered


def test_hardening_checklist_mentions_required_topics() -> None:
    lowered = _normalized(CHECKLIST_PATH)
    for required_text in (
        "access control",
        "api gateway",
        "cors",
        "request size",
        "timeout",
        "filesystem roots",
        "artifact downloads",
        "error sanitization",
        "logging",
        "sqlite",
        "coze base url",
        "rollback tags",
    ):
        assert required_text in lowered
