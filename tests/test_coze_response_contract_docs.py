from pathlib import Path


def test_phase_4_coze_response_contract_doc_exists_and_names_required_fields() -> None:
    doc_path = Path("docs/phase-4-coze-response-contract.md")

    assert doc_path.is_file()
    text = doc_path.read_text(encoding="utf-8")

    for required_text in (
        "task_id",
        "analysis_method",
        "formal_de_method",
        "threshold_summary",
        "top_genes_by_padj",
        "top_genes_by_abs_log2fc",
        "warnings",
        "limitations",
        "should not claim pathway enrichment",
        "should not invent gene annotations",
    ):
        assert required_text in text
