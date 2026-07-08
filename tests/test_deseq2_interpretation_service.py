import json
from pathlib import Path

from backend.app.services.deseq2_interpretation import (
    INTERPRETATION_BOUNDARY,
    build_deseq2_interpretation_contract,
    classify_deseq2_gene,
    parse_deseq2_results,
    summarize_deseq2_results,
)


FORBIDDEN_PUBLIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "token",
    "password",
    "secret",
)


def _assert_no_forbidden_public_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_PUBLIC_FRAGMENTS)


def _write_results(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "gene_id,baseMean,log2FoldChange,lfcSE,stat,pvalue,padj",
                "GeneStrongUp,100,2.0,0.2,10,0.0001,0.001",
                "GeneStrongDown,80,-1.5,0.3,-5,0.002,0.02",
                "GeneSmallEffect,60,0.5,0.2,2.5,0.01,0.03",
                "GeneLargeNoPadj,50,2.5,0.4,6,0.02,NA",
                "GeneNoLog2FC,30,NA,0.5,NA,NA,NA",
                r"D:\secret\token_gene,10,0,0.1,0,0.9,0.99",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_valid_deseq2_results_are_summarized_deterministically(tmp_path: Path) -> None:
    results_path = tmp_path / "deseq2_results.csv"
    _write_results(results_path)

    first = summarize_deseq2_results(results_path)
    second = summarize_deseq2_results(results_path)

    assert first == second
    assert first["analysis_method"] == "deseq2"
    assert first["formal_de_method"] == "deseq2"
    assert first["statistical_test_performed"] is True
    assert first["pvalue_available"] is True
    assert first["adjusted_pvalue_available"] is True
    assert first["total_genes_tested"] == 6
    assert first["interpretation_boundary"] == INTERPRETATION_BOUNDARY
    _assert_no_forbidden_public_fragments(first)


def test_threshold_counting_and_direction_classification(tmp_path: Path) -> None:
    results_path = tmp_path / "deseq2_results.csv"
    _write_results(results_path)

    summary = summarize_deseq2_results(results_path)

    assert summary["padj_threshold"] == 0.05
    assert summary["abs_log2fc_threshold"] == 1.0
    assert summary["genes_with_valid_padj"] == 4
    assert summary["genes_with_na_padj"] == 2
    assert summary["genes_passing_padj_threshold"] == 3
    assert summary["genes_passing_log2fc_threshold"] == 3
    assert summary["genes_passing_both_thresholds"] == 2
    assert summary["genes_passing_default_reporting_filter"] == 2
    assert summary["upregulated_count"] == 1
    assert summary["downregulated_count"] == 1

    up = classify_deseq2_gene(
        {"gene_id": "up", "log2FoldChange": 1.2, "padj": 0.01},
        0.05,
        1.0,
    )
    down = classify_deseq2_gene(
        {"gene_id": "down", "log2FoldChange": -1.2, "padj": 0.01},
        0.05,
        1.0,
    )
    zero = classify_deseq2_gene(
        {"gene_id": "zero", "log2FoldChange": 0, "padj": 0.01},
        0.05,
        1.0,
    )
    unknown = classify_deseq2_gene(
        {"gene_id": "unknown", "log2FoldChange": None, "padj": None},
        0.05,
        1.0,
    )

    assert up["direction"] == "up"
    assert down["direction"] == "down"
    assert zero["direction"] == "unchanged_or_zero"
    assert unknown["direction"] == "unknown"


def test_top_gene_sorting_handles_na_values_safely(tmp_path: Path) -> None:
    results_path = tmp_path / "deseq2_results.csv"
    _write_results(results_path)

    summary = summarize_deseq2_results(results_path)

    assert [gene["gene_id"] for gene in summary["top_genes_by_padj"]][:3] == [
        "GeneStrongUp",
        "GeneStrongDown",
        "GeneSmallEffect",
    ]
    assert all(gene["padj"] is not None for gene in summary["top_genes_by_padj"])
    assert [gene["gene_id"] for gene in summary["top_genes_by_abs_log2fc"]][:3] == [
        "GeneLargeNoPadj",
        "GeneStrongUp",
        "GeneStrongDown",
    ]
    assert all(
        gene["log2FoldChange"] is not None
        for gene in summary["top_genes_by_abs_log2fc"]
    )


def test_parse_handles_na_pvalue_and_padj(tmp_path: Path) -> None:
    results_path = tmp_path / "deseq2_results.csv"
    _write_results(results_path)

    rows = parse_deseq2_results(results_path)
    row_by_gene = {row["gene_id"]: row for row in rows}

    assert row_by_gene["GeneLargeNoPadj"]["padj"] is None
    assert row_by_gene["GeneNoLog2FC"]["pvalue"] is None
    assert row_by_gene["GeneNoLog2FC"]["log2FoldChange"] is None
    _assert_no_forbidden_public_fragments(rows)


def test_summary_contains_warnings_limitations_and_contract(tmp_path: Path) -> None:
    results_path = tmp_path / "deseq2_results.csv"
    _write_results(results_path)

    summary = summarize_deseq2_results(results_path)
    contract = build_deseq2_interpretation_contract(summary)

    assert summary["interpretation_warnings"]
    assert summary["interpretation_limitations"]
    assert "NA pvalue or padj" in " ".join(summary["interpretation_warnings"])
    assert "Statistical significance is not the same as biological significance." in " ".join(
        summary["interpretation_limitations"]
    )
    assert contract["threshold_summary"]["genes_passing_default_reporting_filter"] == 2
    assert contract["interpretation_boundary"] == INTERPRETATION_BOUNDARY
    assert contract["recommended_next_steps"]
    _assert_no_forbidden_public_fragments(contract)
