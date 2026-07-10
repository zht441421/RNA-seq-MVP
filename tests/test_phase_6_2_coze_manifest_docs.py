from pathlib import Path


DOC_PATH = Path("docs/phase-6-2-coze-plugin-manifest-preparation.md")


def test_phase_6_2_coze_manifest_doc_exists() -> None:
    assert DOC_PATH.is_file()


def test_phase_6_2_coze_manifest_doc_mentions_required_topics() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")
    lowered = text.lower()

    for required_text in (
        "plugin/manifest preparation",
        "recommended endpoint sequence",
        "coze-summary",
        "artifact download",
        "input registration",
        "contrast direction",
        "deseq2 preflight",
        "safety boundaries",
        "no real coze api call in this phase",
        "no frontend in this phase",
        "no local absolute paths",
    ):
        assert required_text in lowered
