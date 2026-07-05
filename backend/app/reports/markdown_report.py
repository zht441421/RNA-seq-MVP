from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.qc_report import QCReport
from backend.app.models.reliability import ReliabilityAssessment


def build_markdown_report(
    plan: AnalysisPlan,
    qc_report: QCReport,
    reliability: ReliabilityAssessment,
    execution_mode: str = "mock",
) -> str:
    conclusion_policy = (
        "Limited strong conclusions are allowed with documented limitations."
        if reliability.strong_conclusion_allowed
        else "Exploratory language only. No definitive biological or clinical conclusions are allowed."
    )
    lines = [
        f"# Bioinformatics Agent Report: {plan.project_id}",
        "",
        "## Execution Mode",
        "",
        _execution_mode_text(execution_mode),
        "",
        "## Analysis Plan",
        "",
        f"- Primary method: {plan.primary_method}",
        f"- Validation methods: {', '.join(plan.validation_methods)}",
        f"- Normalization: {plan.normalization}",
        f"- Design formula: `{plan.design_formula}`",
        f"- FDR threshold: {plan.fdr_threshold}",
        f"- log2FC threshold: {plan.log2fc_threshold}",
        "",
        "## QC Summary",
        "",
        f"- QC passed: {qc_report.passed}",
        f"- Group counts: {qc_report.group_counts}",
        "",
        "## QC Checks",
        "",
    ]
    for check in qc_report.checks:
        lines.append(f"- {check.name}: {check.status.value} ({check.severity.value}) - {check.message}")

    lines.extend(
        [
            "",
            "## Reliability",
            "",
            f"- Grade: {reliability.grade.value}",
            f"- Strong conclusion allowed: {reliability.strong_conclusion_allowed}",
            f"- Language policy: {conclusion_policy}",
            "",
            "## Limitations",
            "",
            _limitation_text(execution_mode),
            "- Any downstream interpretation must follow the reliability grade and documented validation status.",
        ]
    )
    return "\n".join(lines) + "\n"


def _execution_mode_text(execution_mode: str) -> str:
    if execution_mode == "real_r":
        return "Phase 1.1 real R execution path. DESeq2 may be real if primary method completed."
    return "Phase 1 mock execution. No real DESeq2, edgeR, or limma-voom result was generated."


def _limitation_text(execution_mode: str) -> str:
    if execution_mode == "real_r":
        return "- Real analysis outputs require validation and reliability gating before strong conclusions."
    return "- This is an MVP mock run."
