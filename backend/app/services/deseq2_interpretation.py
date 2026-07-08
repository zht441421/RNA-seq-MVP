import csv
import math
from pathlib import Path, PurePosixPath, PureWindowsPath


ANALYSIS_METHOD = "deseq2"
DEFAULT_PADJ_THRESHOLD = 0.05
DEFAULT_ABS_LOG2FC_THRESHOLD = 1.0
INTERPRETATION_BOUNDARY = (
    "Statistical significance does not automatically imply biological significance."
)
_TOP_GENE_LIMIT = 10
_NA_VALUES = {"", "na", "nan", "null", "none"}


def parse_deseq2_results(results_csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with results_csv_path.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        for row in reader:
            if row is None:
                continue
            rows.append(
                {
                    "gene_id": _safe_public_text(row.get("gene_id", "")),
                    "baseMean": _parse_optional_float(row.get("baseMean")),
                    "log2FoldChange": _parse_optional_float(row.get("log2FoldChange")),
                    "lfcSE": _parse_optional_float(row.get("lfcSE")),
                    "stat": _parse_optional_float(row.get("stat")),
                    "pvalue": _parse_optional_float(row.get("pvalue")),
                    "padj": _parse_optional_float(row.get("padj")),
                }
            )
    return rows


def summarize_deseq2_results(
    results_csv_path: Path,
    padj_threshold: float = DEFAULT_PADJ_THRESHOLD,
    abs_log2fc_threshold: float = DEFAULT_ABS_LOG2FC_THRESHOLD,
) -> dict:
    safe_padj_threshold = _safe_threshold(padj_threshold, DEFAULT_PADJ_THRESHOLD)
    safe_abs_log2fc_threshold = _safe_threshold(
        abs_log2fc_threshold,
        DEFAULT_ABS_LOG2FC_THRESHOLD,
    )
    rows = parse_deseq2_results(results_csv_path)
    classified_rows = [
        classify_deseq2_gene(row, safe_padj_threshold, safe_abs_log2fc_threshold)
        for row in rows
    ]

    genes_with_valid_padj = [
        row for row in classified_rows if row["padj"] is not None
    ]
    genes_with_na_padj = [
        row for row in classified_rows if row["padj"] is None
    ]
    genes_passing_padj = [
        row for row in classified_rows if row["significant_by_padj"]
    ]
    genes_passing_log2fc = [
        row for row in classified_rows if row["large_effect_by_log2fc"]
    ]
    genes_passing_both = [
        row for row in classified_rows if row["passes_default_reporting_filter"]
    ]

    return {
        "analysis_method": ANALYSIS_METHOD,
        "formal_de_method": ANALYSIS_METHOD,
        "statistical_test_performed": True,
        "pvalue_available": True,
        "adjusted_pvalue_available": True,
        "padj_threshold": safe_padj_threshold,
        "abs_log2fc_threshold": safe_abs_log2fc_threshold,
        "total_genes_tested": len(classified_rows),
        "genes_with_valid_padj": len(genes_with_valid_padj),
        "genes_with_na_padj": len(genes_with_na_padj),
        "genes_passing_padj_threshold": len(genes_passing_padj),
        "genes_passing_log2fc_threshold": len(genes_passing_log2fc),
        "genes_passing_both_thresholds": len(genes_passing_both),
        "genes_passing_default_reporting_filter": len(genes_passing_both),
        "upregulated_count": len(
            [row for row in genes_passing_both if row["direction"] == "up"]
        ),
        "downregulated_count": len(
            [row for row in genes_passing_both if row["direction"] == "down"]
        ),
        "top_genes_by_padj": _top_genes_by_padj(classified_rows),
        "top_genes_by_abs_log2fc": _top_genes_by_abs_log2fc(classified_rows),
        "interpretation_warnings": _interpretation_warnings(classified_rows),
        "interpretation_limitations": _interpretation_limitations(),
        "safe_human_readable_notes": _safe_human_readable_notes(),
        "interpretation_boundary": INTERPRETATION_BOUNDARY,
    }


def classify_deseq2_gene(
    row: dict,
    padj_threshold: float,
    abs_log2fc_threshold: float,
) -> dict:
    padj = _coerce_optional_float(row.get("padj"))
    log2fc = _coerce_optional_float(row.get("log2FoldChange"))
    significant_by_padj = padj is not None and padj <= padj_threshold
    large_effect_by_log2fc = (
        log2fc is not None and abs(log2fc) >= abs_log2fc_threshold
    )
    return {
        "gene_id": _safe_public_text(row.get("gene_id", "")),
        "baseMean": _coerce_optional_float(row.get("baseMean")),
        "log2FoldChange": log2fc,
        "lfcSE": _coerce_optional_float(row.get("lfcSE")),
        "stat": _coerce_optional_float(row.get("stat")),
        "pvalue": _coerce_optional_float(row.get("pvalue")),
        "padj": padj,
        "significant_by_padj": significant_by_padj,
        "large_effect_by_log2fc": large_effect_by_log2fc,
        "passes_default_reporting_filter": (
            significant_by_padj and large_effect_by_log2fc
        ),
        "direction": _direction_for_log2fc(log2fc),
        "direction_label": _direction_label_for_log2fc(log2fc),
    }


def build_deseq2_interpretation_contract(summary: dict) -> dict:
    return {
        "analysis_method": ANALYSIS_METHOD,
        "formal_de_method": ANALYSIS_METHOD,
        "status": "deseq2_interpretation_summary_ready",
        "summary": dict(summary),
        "threshold_summary": {
            "padj_threshold": summary.get("padj_threshold"),
            "abs_log2fc_threshold": summary.get("abs_log2fc_threshold"),
            "genes_passing_default_reporting_filter": summary.get(
                "genes_passing_default_reporting_filter",
                summary.get("genes_passing_both_thresholds", 0),
            ),
        },
        "interpretation_boundary": INTERPRETATION_BOUNDARY,
        "warnings": list(summary.get("interpretation_warnings", [])),
        "limitations": list(summary.get("interpretation_limitations", [])),
        "recommended_next_steps": [
            "Review the experimental design and DESeq2 contrast/reference levels.",
            "Inspect genes with NA pvalue or padj before interpreting filtered results.",
            "Use biological context and independent validation before making conclusions.",
        ],
    }


def _top_genes_by_padj(rows: list[dict]) -> list[dict]:
    ranked = sorted(
        [row for row in rows if row["padj"] is not None],
        key=lambda row: (row["padj"], _safe_abs(row["log2FoldChange"]), row["gene_id"]),
    )
    return [_public_gene_entry(row) for row in ranked[:_TOP_GENE_LIMIT]]


def _top_genes_by_abs_log2fc(rows: list[dict]) -> list[dict]:
    ranked = sorted(
        [row for row in rows if row["log2FoldChange"] is not None],
        key=lambda row: (-abs(row["log2FoldChange"]), row["gene_id"]),
    )
    return [_public_gene_entry(row) for row in ranked[:_TOP_GENE_LIMIT]]


def _public_gene_entry(row: dict) -> dict:
    return {
        "gene_id": row["gene_id"],
        "baseMean": row["baseMean"],
        "log2FoldChange": row["log2FoldChange"],
        "pvalue": row["pvalue"],
        "padj": row["padj"],
        "significant_by_padj": row["significant_by_padj"],
        "large_effect_by_log2fc": row["large_effect_by_log2fc"],
        "passes_default_reporting_filter": row["passes_default_reporting_filter"],
        "direction": row["direction"],
        "direction_label": row["direction_label"],
    }


def _interpretation_warnings(rows: list[dict]) -> list[str]:
    warnings = [
        "log2FoldChange direction depends on DESeq2 contrast/reference level; this summary reports positive and negative log2FoldChange only.",
        INTERPRETATION_BOUNDARY,
    ]
    if any(row["padj"] is None for row in rows):
        warnings.append(
            "NA pvalue or padj can occur due to filtering, low counts, outlier handling, or model limitations."
        )
    return warnings


def _interpretation_limitations() -> list[str]:
    return [
        "Adjusted p-values control false discovery rate under the statistical model.",
        "Statistical significance is not the same as biological significance.",
        "log2FoldChange direction depends on DESeq2 contrast/reference level.",
        "No batch correction or complex design was performed in this phase.",
        "No GO/KEGG/GSEA enrichment analysis was performed.",
        "Do not infer causal biology, clinical significance, pathway enrichment, or gene annotation from this summary alone.",
    ]


def _safe_human_readable_notes() -> list[str]:
    return [
        "Genes passing both thresholds are reporting candidates, not final biological conclusions.",
        "Positive log2FoldChange and negative log2FoldChange are reported without asserting treatment/control direction.",
        "Missing pvalue or padj values are preserved in the counts and excluded from adjusted-p-value ranking.",
    ]


def _direction_for_log2fc(log2fc: float | None) -> str:
    if log2fc is None:
        return "unknown"
    if log2fc > 0:
        return "up"
    if log2fc < 0:
        return "down"
    return "unchanged_or_zero"


def _direction_label_for_log2fc(log2fc: float | None) -> str:
    if log2fc is None:
        return "unknown log2FoldChange"
    if log2fc > 0:
        return "positive log2FoldChange"
    if log2fc < 0:
        return "negative log2FoldChange"
    return "zero log2FoldChange"


def _parse_optional_float(value: object) -> float | None:
    return _coerce_optional_float(value)


def _coerce_optional_float(value: object) -> float | None:
    text = "" if value is None else str(value).strip()
    if text.lower() in _NA_VALUES:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_threshold(value: object, default: float) -> float:
    number = _coerce_optional_float(value)
    if number is None or number < 0:
        return default
    return number


def _safe_abs(value: float | None) -> float:
    return abs(value) if value is not None else -1.0


def _safe_public_text(value: object) -> str:
    text = str(value or "").strip()
    for fragment in ("traceback", "token", "password", "secret"):
        text = text.replace(fragment, "redacted")
        text = text.replace(fragment.title(), "redacted")
        text = text.replace(fragment.upper(), "redacted")
    if _looks_like_absolute_path(text):
        return PurePosixPath(text.replace("\\", "/")).name or "redacted"
    return text


def _looks_like_absolute_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(normalized)
    return bool(
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or normalized.startswith("/home/")
        or normalized.startswith("/mnt/")
    )
