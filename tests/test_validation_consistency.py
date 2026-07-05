import csv
from pathlib import Path

from backend.app.services.validation_comparison import compute_validation_comparison


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_validation_consistency_scores_direction_agreement(tmp_path: Path) -> None:
    deseq2 = tmp_path / "deseq2_results.csv"
    edger = tmp_path / "edger_results.csv"
    limma = tmp_path / "limma_voom_results.csv"
    output = tmp_path / "validation_comparison.csv"
    write_csv(
        deseq2,
        [
            {"gene_id": "GeneA", "log2FoldChange": 2.0, "padj": 0.01},
            {"gene_id": "GeneB", "log2FoldChange": -1.5, "padj": 0.02},
            {"gene_id": "GeneC", "log2FoldChange": 0.2, "padj": 0.9},
        ],
    )
    write_csv(
        edger,
        [
            {"gene_id": "GeneA", "logFC": 1.8, "FDR": 0.01},
            {"gene_id": "GeneB", "logFC": -1.1, "FDR": 0.03},
            {"gene_id": "GeneC", "logFC": 0.1, "FDR": 0.8},
        ],
    )
    write_csv(
        limma,
        [
            {"gene_id": "GeneA", "logFC": 1.6, "adj.P.Val": 0.02},
            {"gene_id": "GeneB", "logFC": 1.2, "adj.P.Val": 0.04},
            {"gene_id": "GeneC", "logFC": 0.2, "adj.P.Val": 0.7},
        ],
    )

    summary = compute_validation_comparison(
        deseq2_results_path=deseq2,
        edger_results_path=edger,
        limma_results_path=limma,
        output_path=output,
    )

    assert summary["validation_consistency_status"] == "computed"
    assert summary["validation_consistency_score"] == 0.75
    assert summary["comparisons_total"] == 4
    assert output.exists()


def test_validation_consistency_handles_no_significant_genes(tmp_path: Path) -> None:
    deseq2 = tmp_path / "deseq2_results.csv"
    output = tmp_path / "validation_comparison.csv"
    write_csv(
        deseq2,
        [
            {"gene_id": "GeneA", "log2FoldChange": 0.2, "padj": 0.8},
        ],
    )

    summary = compute_validation_comparison(
        deseq2_results_path=deseq2,
        edger_results_path=None,
        limma_results_path=None,
        output_path=output,
    )

    assert summary["validation_consistency_status"] == "insufficient_significant_genes"
    assert summary["validation_consistency_score"] is None

