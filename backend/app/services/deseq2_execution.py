import csv
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from backend.app.services import formal_de_preflight
from backend.app.services.artifact_paths import (
    ensure_task_output_dir,
    get_output_root,
    list_deseq2_artifact_specs,
    resolve_task_artifact_path,
)
from backend.app.services.contrast_validation import resolve_contrast
from backend.app.services.formal_de_preflight import CommandResult, run_command_safely
from backend.app.services.input_validation import validate_rnaseq_input_files
from backend.app.services.deseq2_interpretation import (
    DEFAULT_ABS_LOG2FC_THRESHOLD,
    DEFAULT_PADJ_THRESHOLD,
    INTERPRETATION_BOUNDARY,
    build_deseq2_interpretation_contract,
    summarize_deseq2_results,
)
from backend.app.services.rnaseq_minimal import (
    CountMatrix,
    MinimalRNASeqValidationError,
    build_validation_error,
    read_count_matrix,
    read_metadata,
    reorder_counts_to_metadata,
    validate_minimal_inputs,
    write_json,
)


DESEQ2_PREFLIGHT_NOT_READY = "DESEQ2_PREFLIGHT_NOT_READY"
DESEQ2_EXECUTION_FAILED = "DESEQ2_EXECUTION_FAILED"
DESEQ2_ANALYSIS_METHOD = "deseq2"
_PLACEHOLDER_TIMESTAMP = "2026-01-01T00:00:00Z"
_DESEQ2_TIMEOUT_SECONDS = 120
_DESEQ2_OUTPUT_FILES = [
    "deseq2_results.csv",
    "deseq2_interpretation_summary.json",
    "deseq2_summary.json",
    "deseq2_run_manifest.json",
    "report.md",
]


@dataclass(frozen=True)
class Deseq2ExecutionResult:
    task_id: str
    status: str
    executor_name: str
    started_at: str
    finished_at: str
    duration_seconds: float
    planned_artifacts: list[dict] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    generated_files: list[dict] = field(default_factory=list)


class Deseq2ExecutionError(ValueError):
    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        status_code: int,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        preflight: dict | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.errors = _safe_messages(errors or [message])
        self.warnings = _safe_messages(warnings or [])
        self.preflight = _safe_preflight_summary(preflight or {})
        super().__init__(message)

    def to_detail(self) -> dict:
        detail = {
            "error_code": self.error_code,
            "message": self.message,
            "formal_method": DESEQ2_ANALYSIS_METHOD,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }
        if self.preflight:
            detail["preflight"] = self.preflight
        return detail


class Deseq2PreflightNotReadyError(Deseq2ExecutionError):
    def __init__(self, preflight: dict) -> None:
        super().__init__(
            error_code=DESEQ2_PREFLIGHT_NOT_READY,
            message="DESeq2 execution is not available because the preflight check is not ready.",
            status_code=501,
            errors=[
                "DESeq2 execution is not available because the preflight check is not ready."
            ],
            warnings=preflight.get("warnings", []),
            preflight=preflight,
        )


def execute_task_deseq2(
    *,
    task_id: str,
    metadata_file: str,
    count_matrix_file: str,
    project_name: str = "unspecified",
    omics_type: str = "unspecified",
    contrast_column: str | None = None,
    contrast_numerator: str | None = None,
    contrast_denominator: str | None = None,
    preflight: dict | None = None,
) -> Deseq2ExecutionResult:
    metadata, counts, warnings, metadata_path, count_matrix_path = _load_and_validate_inputs(
        metadata_file=metadata_file,
        count_matrix_file=count_matrix_file,
    )
    try:
        counts = reorder_counts_to_metadata(metadata, counts)
    except ValueError as exc:
        raise build_validation_error([str(exc)], warnings) from exc

    contrast = resolve_contrast(
        metadata,
        contrast_column=contrast_column,
        contrast_numerator=contrast_numerator,
        contrast_denominator=contrast_denominator,
    )
    contrast_payload = contrast.as_dict()

    preflight_result = preflight or formal_de_preflight.run_deseq2_preflight()
    if not preflight_result.get("ready"):
        raise Deseq2PreflightNotReadyError(preflight_result)

    output_dir = ensure_task_output_dir(task_id)
    output_dir_relative = output_dir.relative_to(get_output_root()).as_posix()
    script_path = output_dir / "run_deseq2.R"
    results_path = resolve_task_artifact_path(task_id, "deseq2_results.csv")
    interpretation_path = resolve_task_artifact_path(
        task_id,
        "deseq2_interpretation_summary.json",
    )
    summary_path = resolve_task_artifact_path(task_id, "deseq2_summary.json")
    manifest_path = resolve_task_artifact_path(task_id, "deseq2_run_manifest.json")
    report_path = resolve_task_artifact_path(task_id, "report.md")

    script_path.write_text(_deseq2_r_script(), encoding="utf-8")
    command = [
        "Rscript",
        "--vanilla",
        str(script_path),
        str(metadata_path),
        str(count_matrix_path),
        contrast.contrast_column,
        contrast.contrast_numerator,
        contrast.contrast_denominator,
        str(results_path),
    ]
    command_result = run_command_safely(
        command,
        timeout_seconds=_DESEQ2_TIMEOUT_SECONDS,
        working_directory=output_dir,
    )
    if command_result.returncode != 0:
        raise _execution_failed(command_result)

    if not results_path.is_file():
        raise Deseq2ExecutionError(
            error_code=DESEQ2_EXECUTION_FAILED,
            message="DESeq2 execution failed to produce the expected results file.",
            status_code=500,
            errors=["DESeq2 execution did not produce deseq2_results.csv."],
        )

    interpretation_summary = summarize_deseq2_results(
        results_path,
        contrast=contrast_payload,
    )
    interpretation_contract = build_deseq2_interpretation_contract(
        interpretation_summary,
        contrast=contrast_payload,
    )
    result_gene_count = int(interpretation_summary["total_genes_tested"])
    limitations = _deseq2_limitations()
    generated_files = _generated_file_entries(task_id)
    output_files = [
        artifact["relative_path"]
        for artifact in generated_files
        if artifact["name"] in _DESEQ2_OUTPUT_FILES
    ]
    summary = _deseq2_summary(
        task_id=task_id,
        counts=counts,
        result_gene_count=result_gene_count,
        interpretation_summary=interpretation_summary,
        contrast=contrast_payload,
        warnings=warnings,
        limitations=limitations,
    )
    manifest = _deseq2_manifest(
        task_id=task_id,
        project_name=project_name,
        omics_type=omics_type,
        metadata_file=metadata_file,
        count_matrix_file=count_matrix_file,
        output_dir_relative=output_dir_relative,
        output_files=output_files,
        contrast=contrast_payload,
        limitations=limitations,
    )

    write_json(interpretation_path, interpretation_contract)
    write_json(summary_path, summary)
    write_json(manifest_path, manifest)
    _write_deseq2_report(
        report_path,
        task_id=task_id,
        sample_count=len(counts.sample_ids),
        gene_count=len(counts.gene_ids),
        result_gene_count=result_gene_count,
        interpretation_summary=interpretation_summary,
        contrast=contrast_payload,
        output_files=output_files,
        warnings=warnings,
        limitations=limitations,
    )

    return Deseq2ExecutionResult(
        task_id=task_id,
        status="deseq2_analysis_completed",
        executor_name="deseq2_rscript_executor",
        started_at=_PLACEHOLDER_TIMESTAMP,
        finished_at=_PLACEHOLDER_TIMESTAMP,
        duration_seconds=0.0,
        messages=[
            "DESeq2 formal differential expression executor invoked.",
            f"Prepared task output directory: {output_dir_relative}.",
            "Validated metadata and count matrix inputs.",
            (
                "Ran DESeq2 through Rscript with explicit contrast "
                f"{contrast_payload['direction']}."
            ),
        ],
        warnings=warnings,
        limitations=limitations,
        generated_files=list_deseq2_artifact_specs(task_id),
    )


def _load_and_validate_inputs(
    *,
    metadata_file: str,
    count_matrix_file: str,
) -> tuple[list[dict], CountMatrix, list[str], Path, Path]:
    path_validation = validate_rnaseq_input_files(
        metadata_file=metadata_file,
        count_matrix_file=count_matrix_file,
    )
    if not path_validation.valid:
        raise build_validation_error(path_validation.errors)
    if path_validation.metadata.resolved_path is None:
        raise build_validation_error(["metadata_file could not be resolved under input root."])
    if path_validation.count_matrix.resolved_path is None:
        raise build_validation_error(["count_matrix_file could not be resolved under input root."])

    try:
        metadata = read_metadata(path_validation.metadata.resolved_path)
        counts = read_count_matrix(path_validation.count_matrix.resolved_path)
    except ValueError as exc:
        raise build_validation_error([str(exc)]) from exc

    validation_result = validate_minimal_inputs(metadata, counts)
    warnings = list(validation_result.warnings)
    if not validation_result.valid:
        raise build_validation_error(validation_result.errors, warnings)
    return (
        metadata,
        counts,
        warnings,
        path_validation.metadata.resolved_path,
        path_validation.count_matrix.resolved_path,
    )


def _execution_failed(command_result: CommandResult) -> Deseq2ExecutionError:
    errors = ["DESeq2 execution failed while running Rscript."]
    if command_result.timed_out:
        errors.append("Rscript command timed out.")
    elif command_result.error:
        errors.append(command_result.error)
    elif command_result.stderr:
        errors.append(command_result.stderr)
    elif command_result.stdout:
        errors.append(command_result.stdout)
    return Deseq2ExecutionError(
        error_code=DESEQ2_EXECUTION_FAILED,
        message="DESeq2 execution failed.",
        status_code=500,
        errors=errors,
    )


def _deseq2_summary(
    *,
    task_id: str,
    counts: CountMatrix,
    result_gene_count: int,
    interpretation_summary: dict,
    contrast: dict,
    warnings: list[str],
    limitations: list[str],
) -> dict:
    genes_passing_filter = int(
        interpretation_summary.get("genes_passing_default_reporting_filter", 0)
    )
    return {
        "task_id": task_id,
        "analysis_method": DESEQ2_ANALYSIS_METHOD,
        "formal_de_method": DESEQ2_ANALYSIS_METHOD,
        "formal_de_ready": True,
        "statistical_test_performed": True,
        "pvalue_available": True,
        "adjusted_pvalue_available": True,
        "external_tools_called": True,
        "external_tool": "Rscript",
        "r_package": "DESeq2",
        "design_formula": "~ condition",
        "contrast": contrast,
        "positive_log2fc_interpretation": contrast[
            "positive_log2fc_interpretation"
        ],
        "negative_log2fc_interpretation": contrast[
            "negative_log2fc_interpretation"
        ],
        "input_sample_count": len(counts.sample_ids),
        "input_gene_count": len(counts.gene_ids),
        "result_gene_count": result_gene_count,
        "pvalue_column": "pvalue",
        "adjusted_pvalue_column": "padj",
        "interpretation_summary_file": "deseq2_interpretation_summary.json",
        "default_padj_threshold": DEFAULT_PADJ_THRESHOLD,
        "default_abs_log2fc_threshold": DEFAULT_ABS_LOG2FC_THRESHOLD,
        "genes_passing_default_reporting_filter": genes_passing_filter,
        "top_genes_available": bool(
            interpretation_summary.get("top_genes_by_padj")
            or interpretation_summary.get("top_genes_by_abs_log2fc")
        ),
        "interpretation_boundary": INTERPRETATION_BOUNDARY,
        "limitations": limitations,
        "warnings": warnings,
    }


def _deseq2_manifest(
    *,
    task_id: str,
    project_name: str,
    omics_type: str,
    metadata_file: str,
    count_matrix_file: str,
    output_dir_relative: str,
    output_files: list[str],
    contrast: dict,
    limitations: list[str],
) -> dict:
    return {
        "task_id": task_id,
        "project_name": project_name,
        "omics_type": omics_type,
        "analysis_method": DESEQ2_ANALYSIS_METHOD,
        "execution_mode": "formal_de_real",
        "formal_de_method": DESEQ2_ANALYSIS_METHOD,
        "metadata_file": _safe_relative_path(metadata_file),
        "count_matrix_file": _safe_relative_path(count_matrix_file),
        "output_dir_relative": output_dir_relative,
        "command_invoked_safely": True,
        "shell_used": False,
        "package_installation_attempted": False,
        "contrast": contrast,
        "positive_log2fc_interpretation": contrast[
            "positive_log2fc_interpretation"
        ],
        "negative_log2fc_interpretation": contrast[
            "negative_log2fc_interpretation"
        ],
        "output_files": output_files,
        "limitations": limitations,
    }


def _write_deseq2_report(
    path: Path,
    *,
    task_id: str,
    sample_count: int,
    gene_count: int,
    result_gene_count: int,
    interpretation_summary: dict,
    contrast: dict,
    output_files: list[str],
    warnings: list[str],
    limitations: list[str],
) -> None:
    top_by_padj = interpretation_summary.get("top_genes_by_padj", [])
    top_by_abs_log2fc = interpretation_summary.get("top_genes_by_abs_log2fc", [])
    lines = [
        "# DESeq2 Formal Differential Expression Report",
        "",
        "## Analysis method contract",
        "",
        f"- task_id: `{task_id}`",
        "- Current method: `deseq2`",
        "- Formal DE method: DESeq2",
        "- Statistical test performed: true",
        "- P-values available: true",
        "- Adjusted p-values available: true",
        "- Design formula: `~ condition`",
        (
            "- DESeq2 contrast: "
            f"`{contrast['contrast_column']}`, "
            f"`{contrast['contrast_numerator']}`, "
            f"`{contrast['contrast_denominator']}`"
        ),
        f"- Contrast direction: `{contrast['direction']}`",
        (
            "- Positive log2FoldChange: "
            f"{contrast['positive_log2fc_interpretation']}"
        ),
        (
            "- Negative log2FoldChange: "
            f"{contrast['negative_log2fc_interpretation']}"
        ),
        "- Result artifact: `deseq2_results.csv`",
        "",
        "## Input summary",
        "",
        f"- Sample count: {sample_count}",
        f"- Input gene count: {gene_count}",
        f"- Result gene count: {result_gene_count}",
        "",
        "## DESeq2 interpretation summary",
        "",
        (
            "- Genes passing default reporting filter: "
            f"{interpretation_summary.get('genes_passing_default_reporting_filter', 0)}"
        ),
        (
            "- Genes with valid adjusted p-values: "
            f"{interpretation_summary.get('genes_with_valid_padj', 0)}"
        ),
        (
            "- Genes with NA adjusted p-values: "
            f"{interpretation_summary.get('genes_with_na_padj', 0)}"
        ),
        f"- Positive log2FoldChange count: {interpretation_summary.get('upregulated_count', 0)}",
        f"- Negative log2FoldChange count: {interpretation_summary.get('downregulated_count', 0)}",
        "",
        "## Thresholds used",
        "",
        f"- padj <= {interpretation_summary.get('padj_threshold', DEFAULT_PADJ_THRESHOLD)}",
        (
            "- abs(log2FoldChange) >= "
            f"{interpretation_summary.get('abs_log2fc_threshold', DEFAULT_ABS_LOG2FC_THRESHOLD)}"
        ),
        "",
        "## Top genes by adjusted p-value",
        "",
        *_format_gene_bullets(top_by_padj),
        "",
        "## Top genes by absolute log2 fold change",
        "",
        *_format_gene_bullets(top_by_abs_log2fc),
        "",
        "## Important interpretation boundaries",
        "",
        "- Adjusted p-values control false discovery rate under the statistical model.",
        "- Statistical significance is not the same as biological significance.",
        "- log2FoldChange direction depends on DESeq2 contrast/reference level.",
        "- NA pvalue or padj can occur due to filtering, low counts, outlier handling, or model limitations.",
        "- No batch correction or complex design was performed in this phase.",
        "- No GO/KEGG/GSEA enrichment analysis was performed.",
        "- Do not claim causal biology, pathway enrichment, clinical significance, or gene annotations from this result alone.",
        "",
        "## Generated artifacts",
        "",
        *[f"- `{output_file}`" for output_file in output_files],
        "",
        "## Warnings",
        "",
        *([f"- {warning}" for warning in warnings] if warnings else ["- none"]),
        "",
        "## Limitations",
        "",
        *[f"- {limitation}" for limitation in limitations],
        "",
        "## Recommended review",
        "",
        "- Interpret differential expression in biological and experimental context.",
        "- Review sample metadata and condition labels before using the result table.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _deseq2_r_script() -> str:
    return "\n".join(
        [
            "args <- commandArgs(trailingOnly = TRUE)",
            (
                "if (length(args) != 6) { "
                "stop('Expected metadata, counts, contrast column, numerator, denominator, and output.') "
                "}"
            ),
            "metadata_path <- args[[1]]",
            "counts_path <- args[[2]]",
            "contrast_column <- args[[3]]",
            "contrast_numerator <- args[[4]]",
            "contrast_denominator <- args[[5]]",
            "output_path <- args[[6]]",
            "suppressPackageStartupMessages(library(DESeq2))",
            "metadata <- read.csv(metadata_path, stringsAsFactors = TRUE, check.names = FALSE)",
            "counts <- read.csv(counts_path, check.names = FALSE)",
            "if (!('sample_id' %in% colnames(metadata))) { stop('metadata is missing sample_id') }",
            "if (!('condition' %in% colnames(metadata))) { stop('metadata is missing condition') }",
            "if (!('gene_id' %in% colnames(counts))) { stop('counts is missing gene_id') }",
            (
                "if (!(contrast_column %in% colnames(metadata))) { "
                "stop('metadata is missing contrast column') "
                "}"
            ),
            (
                "contrast_values <- unique(as.character(metadata[[contrast_column]]))"
            ),
            "if (length(contrast_values) != 2) { stop('exactly two contrast groups are required') }",
            (
                "if (!(contrast_numerator %in% contrast_values)) { "
                "stop('contrast numerator is missing from metadata') "
                "}"
            ),
            (
                "if (!(contrast_denominator %in% contrast_values)) { "
                "stop('contrast denominator is missing from metadata') "
                "}"
            ),
            (
                "if (contrast_numerator == contrast_denominator) { "
                "stop('contrast numerator and denominator must differ') "
                "}"
            ),
            "rownames(metadata) <- as.character(metadata$sample_id)",
            "rownames(counts) <- as.character(counts$gene_id)",
            "counts$gene_id <- NULL",
            "missing_samples <- setdiff(rownames(metadata), colnames(counts))",
            "extra_samples <- setdiff(colnames(counts), rownames(metadata))",
            "if (length(missing_samples) > 0 || length(extra_samples) > 0) { stop('sample IDs do not align') }",
            "counts <- counts[, rownames(metadata), drop = FALSE]",
            "count_matrix <- as.matrix(counts)",
            "storage.mode(count_matrix) <- 'integer'",
            "metadata[[contrast_column]] <- factor(metadata[[contrast_column]])",
            "design_formula <- as.formula(paste('~', contrast_column))",
            "dds <- DESeqDataSetFromMatrix(countData = count_matrix, colData = metadata, design = design_formula)",
            "dds <- DESeq(dds)",
            "res <- results(dds, contrast = c(contrast_column, contrast_numerator, contrast_denominator))",
            "output <- data.frame(gene_id = rownames(res), as.data.frame(res), check.names = FALSE)",
            "write.csv(output, output_path, row.names = FALSE, na = '')",
        ]
    ) + "\n"


def _format_gene_bullets(genes: list[dict]) -> list[str]:
    if not genes:
        return ["- none"]
    return [
        (
            f"- `{gene['gene_id']}`: padj={_format_optional_number(gene.get('padj'))}, "
            f"log2FoldChange={_format_optional_number(gene.get('log2FoldChange'))}, "
            f"direction={gene.get('direction_label', 'unknown log2FoldChange')}"
        )
        for gene in genes[:5]
    ]


def _format_optional_number(value: object) -> str:
    if value is None:
        return "NA"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NA"
    return f"{number:.6g}"


def _generated_file_entries(task_id: str) -> list[dict]:
    return [
        {
            "name": spec["name"],
            "relative_path": spec["relative_path"],
            "artifact_type": spec["artifact_type"],
            "description": spec["description"],
        }
        for spec in list_deseq2_artifact_specs(task_id)
        if spec["name"] in _DESEQ2_OUTPUT_FILES
    ]


def _count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as input_file:
        return sum(1 for _ in csv.DictReader(input_file))


def _deseq2_limitations() -> list[str]:
    return [
        "DESeq2 was run with the minimal Phase 4.7 design formula: ~ condition.",
        "No batch correction is performed unless future metadata and model support are added.",
        "No complex design, interaction model, paired design, or covariate adjustment is implemented yet.",
        "No GO/KEGG/GSEA enrichment analysis is performed.",
        "Interpretation requires biological and experimental context.",
    ]


def _safe_preflight_summary(preflight: dict) -> dict:
    if not preflight:
        return {}
    return {
        "ready": bool(preflight.get("ready")),
        "formal_method": DESEQ2_ANALYSIS_METHOD,
        "checks": {
            "r_available": bool(preflight.get("r_available")),
            "rscript_available": bool(preflight.get("rscript_available")),
            "biocmanager_available": bool(preflight.get("biocmanager_available")),
            "deseq2_available": bool(preflight.get("deseq2_available")),
        },
        "limitations": _safe_messages(preflight.get("limitations", [])),
    }


def _safe_messages(messages: object) -> list[str]:
    if not isinstance(messages, list):
        messages = [str(messages)]
    return [_sanitize_public_text(message) for message in messages if str(message or "").strip()]


def _sanitize_public_text(value: object) -> str:
    text = str(value or "")
    for fragment in ("traceback", "token", "password", "secret"):
        text = text.replace(fragment, "redacted")
        text = text.replace(fragment.title(), "redacted")
        text = text.replace(fragment.upper(), "redacted")
    words = []
    for word in text.split():
        if _looks_like_absolute_path(word):
            words.append("[redacted-path]")
        else:
            words.append(word)
    return " ".join(words)


def _safe_relative_path(value: object) -> str:
    path_text = str(value or "").strip().replace("\\", "/")
    if not path_text:
        return ""
    posix_path = PurePosixPath(path_text)
    windows_path = PureWindowsPath(path_text)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    ):
        return PurePosixPath(path_text).name or "redacted"
    return posix_path.as_posix()


def _looks_like_absolute_path(value: str) -> bool:
    normalized = value.replace("\\", "/").strip(".,;:'\"()[]{}")
    return (
        len(normalized) > 2
        and normalized[1:3] == ":/"
        or normalized.startswith("/home/")
        or normalized.startswith("/mnt/")
    )
