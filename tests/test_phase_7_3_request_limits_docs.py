from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_7_3_docs_and_readme_cover_required_topics() -> None:
    doc = ROOT / "docs" / "phase-7-3-request-limits-timeout-hardening.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8").lower()
    for phrase in (
        "bioinfo_max_request_bytes",
        "bioinfo_request_timeout_seconds",
        "bioinfo_max_metadata_bytes",
        "bioinfo_max_count_matrix_bytes",
        "http 413",
        "timeout",
        "reverse proxy",
        "api gateway",
        "uvicorn",
        "coze",
        "artifact download",
        "deseq2 subprocess",
        "no rate limiting",
    ):
        assert phrase in text
    assert "phase 7.3" in (ROOT / "README.md").read_text(encoding="utf-8").lower()
