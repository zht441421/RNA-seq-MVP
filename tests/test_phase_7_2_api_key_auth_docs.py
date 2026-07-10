from pathlib import Path


DOC_PATH = Path("docs/phase-7-2-api-key-auth-scaffold.md")
README_PATH = Path("README.md")


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_phase_7_2_doc_exists_and_readme_mentions_phase() -> None:
    assert DOC_PATH.is_file()
    readme = _normalized(README_PATH)
    assert "phase 7.2 optional api key auth scaffold" in readme
    assert "docs/phase-7-2-api-key-auth-scaffold.md" in readme


def test_phase_7_2_doc_mentions_required_topics() -> None:
    lowered = _normalized(DOC_PATH)
    for phrase in (
        "disabled by default",
        "bioinfo_require_api_key",
        "bioinfo_api_key",
        "bioinfo_api_key_header",
        "x-bioinfo-api-key",
        "constant-time comparison",
        "health",
        "openapi policy",
        "sanitized 401",
        "fails safely",
        "no secrets in responses/logs",
        "reverse proxy/api gateway compatibility",
        "coze",
        "known limitations",
    ):
        assert phrase in lowered
