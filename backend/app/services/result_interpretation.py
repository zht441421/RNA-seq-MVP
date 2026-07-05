import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.config import get_settings
from backend.app.models.reliability import ReliabilityAssessment


FORBIDDEN_AUTOINTERPRETATION_TERMS = [
    "证明",
    "驱动",
    "机制",
    "关键致病基因",
    "确定",
    "confirmed",
    "causal",
]

STRONG_CONCLUSION_WARNING = "当前证据不足以支持强科研结论。"
METHOD_WARNING = "主分析已完成，但存在方法学 warning，请谨慎解释结果。"


def build_result_interpretation(
    project_id: str,
    reliability: Optional[ReliabilityAssessment] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    artifact_root: Optional[Path] = None,
    top_n: int = 10,
) -> Dict[str, Any]:
    artifact_root = artifact_root or get_settings().project_root / "artifacts" / project_id
    result_summary = result_summary or {}
    run_status = _load_run_status(artifact_root, result_summary)
    grade = _reliability_grade(reliability, artifact_root)
    primary_status = run_status.get("primary_method_status")
    run_failed = _status_value(result_summary.get("status")) == "failed" or primary_status == "failed"

    strong_allowed = bool(reliability.strong_conclusion_allowed) if reliability else grade in {"A", "B"}
    if grade in {"C", "D", "E", None} or primary_status == "completed_with_warning":
        strong_allowed = False
    interpretation_allowed = not run_failed and grade != "E"

    guardrails = _guardrails(
        grade=grade,
        primary_status=primary_status,
        strong_conclusion_allowed=strong_allowed,
    )
    base = {
        "interpretation_allowed": interpretation_allowed,
        "strong_conclusion_allowed": strong_allowed,
        "reliability_grade": grade,
        "primary_method_status": primary_status,
        "warnings": run_status.get("warnings") or [],
        "errors": run_status.get("errors") or [],
        "summary": _empty_summary(run_status),
        "top_genes": [],
        "top_genes_label": "Top candidate statistical signals",
        "guardrails": guardrails,
    }

    if not interpretation_allowed:
        base["failure_reason"] = _failure_reason(run_status, grade)
        return base

    deseq2_rows = _read_csv(artifact_root / "04_main_results" / "deseq2_results.csv")
    comparison_rows = _read_csv(artifact_root / "05_validation_results" / "validation_comparison.csv")
    comparison_by_gene = {str(row.get("gene_id", "")): row for row in comparison_rows}
    config = _load_analysis_config(artifact_root)
    fdr_threshold = _float_or(config.get("fdr_threshold"), 0.05)
    log2fc_threshold = _float_or(config.get("log2fc_threshold"), 1.0)
    significant_rows = [
        row for row in deseq2_rows if _is_significant(row, fdr_threshold, log2fc_threshold)
    ]
    upregulated = [
        row for row in significant_rows if _float_or(row.get("log2FoldChange"), 0.0) > 0
    ]
    downregulated = [
        row for row in significant_rows if _float_or(row.get("log2FoldChange"), 0.0) < 0
    ]

    base["summary"] = {
        "deseq2_total_genes": len(deseq2_rows),
        "deseq2_significant_genes": len(significant_rows),
        "upregulated_genes": len(upregulated),
        "downregulated_genes": len(downregulated),
        "fdr_threshold": fdr_threshold,
        "log2fc_threshold": log2fc_threshold,
        "validation_consistency_score": _nullable_float(run_status.get("validation_consistency_score")),
    }
    base["top_genes"] = [
        _top_gene_payload(row, comparison_by_gene.get(str(row.get("gene_id", "")), {}))
        for row in _rank_rows(significant_rows)[:top_n]
    ]
    return base


def write_interpretation_summary_md(artifact_root: Path, interpretation: Dict[str, Any]) -> Path:
    path = artifact_root / "12_interpretation_summary.md"
    summary = interpretation.get("summary") or {}
    lines = [
        "# Result Interpretation Summary",
        "",
        f"- interpretation_allowed: {interpretation.get('interpretation_allowed')}",
        f"- strong_conclusion_allowed: {interpretation.get('strong_conclusion_allowed')}",
        f"- reliability_grade: {interpretation.get('reliability_grade')}",
        f"- primary_method_status: {interpretation.get('primary_method_status')}",
        f"- total genes: {summary.get('deseq2_total_genes')}",
        f"- significant genes: {summary.get('deseq2_significant_genes')}",
        f"- upregulated genes: {summary.get('upregulated_genes')}",
        f"- downregulated genes: {summary.get('downregulated_genes')}",
        f"- validation_consistency_score: {summary.get('validation_consistency_score')}",
        "",
        "## Top candidate statistical signals",
        "",
    ]
    top_genes = interpretation.get("top_genes") or []
    if top_genes:
        for gene in top_genes:
            lines.append(
                "- {gene_id}: log2FoldChange={log2FoldChange}, padj={padj}, direction={direction}, method_support={method_support}".format(
                    gene_id=gene.get("gene_id"),
                    log2FoldChange=gene.get("log2FoldChange"),
                    padj=gene.get("padj"),
                    direction=gene.get("direction"),
                    method_support=", ".join(gene.get("method_support") or []),
                )
            )
    else:
        lines.append("- No candidate statistical signals are shown for this run.")
    lines.extend(["", "## Guardrails", ""])
    for guardrail in interpretation.get("guardrails") or []:
        lines.append(f"- {guardrail}")
    lines.extend(
        [
            "",
            "These entries are ranked statistical signals and candidate differentially expressed genes. Biological validation and domain review are required before interpretation beyond the statistical result table.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _empty_summary(run_status: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "deseq2_total_genes": 0,
        "deseq2_significant_genes": 0,
        "upregulated_genes": 0,
        "downregulated_genes": 0,
        "fdr_threshold": None,
        "log2fc_threshold": None,
        "validation_consistency_score": _nullable_float(run_status.get("validation_consistency_score")),
    }


def _guardrails(
    grade: Optional[str],
    primary_status: Optional[str],
    strong_conclusion_allowed: bool,
) -> List[str]:
    guardrails = [
        "These are statistical differential expression signals, not validated biological conclusions.",
        "Top genes are candidate differentially expressed genes and require biological validation.",
        "Experimental validation and domain-specific review are required.",
    ]
    if not strong_conclusion_allowed:
        guardrails.append(STRONG_CONCLUSION_WARNING)
    if grade in {"C", "D", "E"}:
        guardrails.append(STRONG_CONCLUSION_WARNING)
    if primary_status == "completed_with_warning":
        guardrails.append(METHOD_WARNING)
        guardrails.append("Because primary_method_status is completed_with_warning, grade A interpretation is not allowed.")
    return _dedupe(guardrails)


def _failure_reason(run_status: Dict[str, Any], grade: Optional[str]) -> str:
    errors = run_status.get("errors") or []
    if errors:
        return "; ".join(str(error) for error in errors)
    if grade == "E":
        return "Reliability grade E does not support result interpretation."
    return "Run did not complete successfully."


def _top_gene_payload(row: Dict[str, Any], comparison: Dict[str, Any]) -> Dict[str, Any]:
    log2fc = _nullable_float(row.get("log2FoldChange"))
    padj = _nullable_float(row.get("padj"))
    support = ["DESeq2"]
    if _validation_supports_gene(comparison, "edger"):
        support.append("edgeR")
    if _validation_supports_gene(comparison, "limma"):
        support.append("limma_voom")
    return {
        "gene_id": row.get("gene_id"),
        "log2FoldChange": log2fc,
        "padj": padj,
        "direction": "up" if (log2fc or 0) > 0 else "down" if (log2fc or 0) < 0 else "flat",
        "method_support": support,
        "interpretation_label": "candidate statistical signal",
    }


def _validation_supports_gene(comparison: Dict[str, Any], method: str) -> bool:
    direction_key = f"{method}_direction_consistent"
    significant_key = f"significant_by_{method}"
    if not _truthy(comparison.get(direction_key)):
        return False
    if significant_key not in comparison:
        return True
    return _truthy(comparison.get(significant_key))


def _rank_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _float_or(row.get("padj"), float("inf")),
            -abs(_float_or(row.get("log2FoldChange"), 0.0)),
            str(row.get("gene_id", "")),
        ),
    )


def _is_significant(row: Dict[str, Any], fdr_threshold: float, log2fc_threshold: float) -> bool:
    explicit = str(row.get("significant", "")).strip().lower()
    if explicit in {"true", "1", "yes"}:
        return True
    if explicit in {"false", "0", "no"}:
        return False
    padj = _nullable_float(row.get("padj"))
    log2fc = _nullable_float(row.get("log2FoldChange"))
    return padj is not None and log2fc is not None and padj <= fdr_threshold and abs(log2fc) >= log2fc_threshold


def _load_run_status(artifact_root: Path, result_summary: Dict[str, Any]) -> Dict[str, Any]:
    run_status = result_summary.get("run_status")
    if isinstance(run_status, dict):
        return run_status
    path = artifact_root / "09_environment" / "run_status.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _reliability_grade(reliability: Optional[ReliabilityAssessment], artifact_root: Path) -> Optional[str]:
    if reliability:
        return reliability.grade.value
    audit_path = artifact_root / "10_audit_log.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        return (audit.get("reliability") or {}).get("grade")
    return None


def _load_analysis_config(artifact_root: Path) -> Dict[str, Any]:
    for path in [
        artifact_root / "09_environment" / "analysis_config.json",
        artifact_root / "08_reproducible_code" / "analysis_config.json",
    ]:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _nullable_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"na", "nan", "null", "none"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _float_or(value: Any, default: float) -> float:
    parsed = _nullable_float(value)
    return default if parsed is None else parsed


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _status_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output
