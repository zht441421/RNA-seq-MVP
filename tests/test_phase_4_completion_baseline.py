from pathlib import Path


BASELINE_DOC = Path("docs/phase-4-completion-baseline.md")
CHECKLIST_DOC = Path("docs/phase-4-release-candidate-checklist.md")


def test_phase_4_completion_baseline_docs_exist() -> None:
    assert BASELINE_DOC.is_file()
    assert CHECKLIST_DOC.is_file()


def test_phase_4_completion_baseline_doc_mentions_required_boundaries() -> None:
    text = BASELINE_DOC.read_text(encoding="utf-8")

    for required_text in (
        "minimal_cpm_log2fc",
        "deseq2",
        "GET /task/formal-de/preflight",
        "deseq2_results.csv",
        "deseq2_interpretation_summary.json",
        "scripts/run_phase_4_9_deseq2_demo.py",
        "no fake p-values",
        "no automatic package installation",
        "edgeR",
        "limma",
        "GO",
        "KEGG",
        "GSEA",
    ):
        assert required_text in text


def test_phase_4_release_candidate_checklist_mentions_required_items() -> None:
    text = CHECKLIST_DOC.read_text(encoding="utf-8")

    for required_text in (
        "Tests passed",
        "preflight",
        "interpretation summary",
        "Coze response contract",
        "No package installation",
    ):
        assert required_text in text
