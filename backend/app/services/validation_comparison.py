import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def compute_validation_comparison(
    deseq2_results_path: Path,
    edger_results_path: Optional[Path],
    limma_results_path: Optional[Path],
    output_path: Path,
    fdr_threshold: float = 0.05,
    log2fc_threshold: float = 1.0,
) -> Dict[str, Any]:
    deseq2_rows = _read_result_rows(deseq2_results_path)
    edger_rows = _index_by_gene(_read_result_rows(edger_results_path) if edger_results_path and edger_results_path.exists() else [])
    limma_rows = _index_by_gene(_read_result_rows(limma_results_path) if limma_results_path and limma_results_path.exists() else [])

    comparison_rows: List[Dict[str, Any]] = []
    comparisons_total = 0
    comparisons_consistent = 0
    significant_gene_count = 0

    for row in deseq2_rows:
        gene_id = _gene_id(row)
        deseq2_log2fc = _float_or_none(_pick(row, ["log2FoldChange", "logFC", "log2fc"]))
        deseq2_fdr = _float_or_none(_pick(row, ["padj", "FDR", "adj.P.Val", "fdr"]))
        significant_by_deseq2 = _is_significant(deseq2_log2fc, deseq2_fdr, fdr_threshold, log2fc_threshold)
        if significant_by_deseq2:
            significant_gene_count += 1

        edger = edger_rows.get(gene_id, {})
        limma = limma_rows.get(gene_id, {})
        edger_logfc = _float_or_none(_pick(edger, ["logFC", "log2FoldChange", "log2fc"]))
        limma_logfc = _float_or_none(_pick(limma, ["logFC", "log2FoldChange", "log2fc"]))
        edger_fdr = _float_or_none(_pick(edger, ["FDR", "padj", "adj.P.Val", "fdr"]))
        limma_fdr = _float_or_none(_pick(limma, ["adj.P.Val", "FDR", "padj", "fdr"]))
        edger_consistent = _direction_consistent(deseq2_log2fc, edger_logfc)
        limma_consistent = _direction_consistent(deseq2_log2fc, limma_logfc)

        if significant_by_deseq2 and edger_logfc is not None:
            comparisons_total += 1
            comparisons_consistent += int(edger_consistent)
        if significant_by_deseq2 and limma_logfc is not None:
            comparisons_total += 1
            comparisons_consistent += int(limma_consistent)

        comparison_rows.append(
            {
                "gene_id": gene_id,
                "deseq2_log2fc": deseq2_log2fc,
                "edger_logfc": edger_logfc,
                "limma_logfc": limma_logfc,
                "significant_by_deseq2": significant_by_deseq2,
                "significant_by_edger": _is_significant(edger_logfc, edger_fdr, fdr_threshold, log2fc_threshold),
                "significant_by_limma": _is_significant(limma_logfc, limma_fdr, fdr_threshold, log2fc_threshold),
                "edger_direction_consistent": edger_consistent,
                "limma_direction_consistent": limma_consistent,
            }
        )

    if significant_gene_count == 0:
        consistency_status = "insufficient_significant_genes"
        consistency_score = None
    elif comparisons_total == 0:
        consistency_status = "no_validation_comparisons"
        consistency_score = None
    else:
        consistency_status = "computed"
        consistency_score = comparisons_consistent / comparisons_total

    _write_comparison(output_path, comparison_rows)
    return {
        "validation_consistency_score": consistency_score,
        "validation_consistency_status": consistency_status,
        "significant_gene_count": significant_gene_count,
        "comparisons_total": comparisons_total,
        "comparisons_consistent": comparisons_consistent,
        "output_path": str(output_path),
    }


def _read_result_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _index_by_gene(rows: Iterable[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    indexed: Dict[str, Dict[str, str]] = {}
    for row in rows:
        indexed[_gene_id(row)] = row
    return indexed


def _gene_id(row: Dict[str, str]) -> str:
    return str(_pick(row, ["gene_id", "gene", "GeneID", "id"]) or "").strip()


def _pick(row: Dict[str, str], candidates: List[str]) -> Optional[str]:
    for candidate in candidates:
        if candidate in row:
            return row[candidate]
    return None


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.upper() == "NA":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _is_significant(logfc: Optional[float], fdr: Optional[float], fdr_threshold: float, log2fc_threshold: float) -> bool:
    return fdr is not None and logfc is not None and fdr <= fdr_threshold and abs(logfc) >= log2fc_threshold


def _direction_consistent(primary_logfc: Optional[float], validation_logfc: Optional[float]) -> Optional[bool]:
    if primary_logfc is None or validation_logfc is None or primary_logfc == 0 or validation_logfc == 0:
        return None
    return (primary_logfc > 0 and validation_logfc > 0) or (primary_logfc < 0 and validation_logfc < 0)


def _write_comparison(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "gene_id",
        "deseq2_log2fc",
        "edger_logfc",
        "limma_logfc",
        "significant_by_deseq2",
        "significant_by_edger",
        "significant_by_limma",
        "edger_direction_consistent",
        "limma_direction_consistent",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
