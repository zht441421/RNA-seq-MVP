import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from backend.app.services.contrast_validation import ContrastSpec, resolve_contrast


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sample_count: int = 0
    gene_count: int = 0
    condition_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class CountMatrix:
    gene_ids: list[str]
    sample_ids: list[str]
    values: dict[str, dict[str, float]]
    gene_id_column: str = "gene_id"
    raw_total_counts: dict[str, float] = field(default_factory=dict)


_REPORT_ARTIFACTS = [
    "run_manifest.json",
    "execution_summary.json",
    "qc_summary.json",
    "normalized_counts_cpm.csv",
    "differential_expression_results.csv",
    "report.md",
]
_TOP_RANKED_GENE_COLUMNS = [
    "gene_id",
    "mean_cpm_group_1",
    "mean_cpm_group_2",
    "log2_fold_change",
    "total_count",
]
_CPM_DECIMAL_PLACES = 4
_LOG2FC_DECIMAL_PLACES = 4
MINIMAL_ANALYSIS_METHOD = "minimal_cpm_log2fc"
DESEQ2_ANALYSIS_METHOD = "deseq2"
MINIMAL_ANALYSIS_METHOD_DISPLAY_NAME = "Minimal CPM + preliminary log2 fold-change ranking"
FORMAL_DE_METHOD_NOT_IMPLEMENTED = "FORMAL_DE_METHOD_NOT_IMPLEMENTED"
UNSUPPORTED_ANALYSIS_METHOD = "ANALYSIS_METHOD_NOT_SUPPORTED"
_SUPPORTED_FUTURE_FORMAL_METHODS = ("deseq2", "edger", "limma")
_NOT_IMPLEMENTED_FORMAL_METHODS = ("edger", "limma")
_FORMAL_METHOD_DISPLAY_NAMES = {
    "deseq2": "DESeq2",
    "edger": "edgeR",
    "limma": "limma",
}
_MINIMAL_METHOD_LIMITATIONS = (
    "This method computes CPM normalization and preliminary group-level log2 fold-change ranking only.",
    "No formal DESeq2, edgeR, or limma statistical model was run.",
    "No formal differential expression statistical test was performed.",
    "No p-values, adjusted p-values, q-values, or false discovery rate estimates are available.",
    "The ranking is exploratory and must not be treated as a final DEG list.",
)


class RNASeqMethodContractError(ValueError):
    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        status_code: int,
        requested_method: str,
        errors: list[str],
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.requested_method = requested_method
        self.errors = [error for error in errors if error] or [message]
        super().__init__(message)

    def to_detail(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "requested_method": self.requested_method,
            "supported_current_methods": [MINIMAL_ANALYSIS_METHOD, DESEQ2_ANALYSIS_METHOD],
            "supported_future_formal_methods": get_supported_formal_methods(),
            "errors": list(self.errors),
        }


def get_supported_formal_methods() -> list[str]:
    return list(_SUPPORTED_FUTURE_FORMAL_METHODS)


def get_minimal_method_contract() -> dict:
    return {
        "analysis_method": MINIMAL_ANALYSIS_METHOD,
        "analysis_method_display_name": MINIMAL_ANALYSIS_METHOD_DISPLAY_NAME,
        "formal_de_method": None,
        "formal_de_ready": False,
        "statistical_test_performed": False,
        "pvalue_available": False,
        "adjusted_pvalue_available": False,
        "external_tools_called": False,
        "method_limitations": list(_MINIMAL_METHOD_LIMITATIONS),
        "next_supported_formal_methods": get_supported_formal_methods(),
    }


def validate_requested_analysis_method(method: str | None) -> str:
    normalized_method = _normalize_method_name(method) or MINIMAL_ANALYSIS_METHOD
    if normalized_method == MINIMAL_ANALYSIS_METHOD:
        return MINIMAL_ANALYSIS_METHOD
    if normalized_method == DESEQ2_ANALYSIS_METHOD:
        return DESEQ2_ANALYSIS_METHOD
    if normalized_method in _NOT_IMPLEMENTED_FORMAL_METHODS:
        raise _formal_method_not_implemented(normalized_method)
    raise _unsupported_analysis_method()


def validate_requested_formal_de_method(method: str | None) -> None:
    normalized_method = _normalize_method_name(method)
    if not normalized_method:
        return
    if normalized_method == DESEQ2_ANALYSIS_METHOD:
        return
    if normalized_method in _NOT_IMPLEMENTED_FORMAL_METHODS:
        raise _formal_method_not_implemented(normalized_method)
    raise RNASeqMethodContractError(
        error_code=UNSUPPORTED_ANALYSIS_METHOD,
        message="Requested formal differential expression method is not supported.",
        status_code=422,
        requested_method=_safe_public_method_name(normalized_method),
        errors=[
            "Only planned formal methods can be requested in the formal_de_method field.",
            "DESeq2, edgeR, and limma are planned but not implemented in this phase.",
        ],
    )


def _formal_method_not_implemented(method: str) -> RNASeqMethodContractError:
    return RNASeqMethodContractError(
        error_code=FORMAL_DE_METHOD_NOT_IMPLEMENTED,
        message="Formal differential expression method is planned but not implemented in this phase.",
        status_code=501,
        requested_method=_safe_public_method_name(method),
        errors=[
            (
                "Requested formal differential expression method "
                f"{_safe_public_method_name(method)!r} is not implemented yet."
            ),
            "No DESeq2, edgeR, limma, Rscript, or external tool execution was started.",
        ],
    )


def _unsupported_analysis_method() -> RNASeqMethodContractError:
    return RNASeqMethodContractError(
        error_code=UNSUPPORTED_ANALYSIS_METHOD,
        message="Requested analysis method is not supported by this execution contract.",
        status_code=422,
        requested_method="unsupported",
        errors=[
            f"Current supported analysis method: {MINIMAL_ANALYSIS_METHOD}.",
            "Future formal methods planned but not implemented: deseq2, edger, limma.",
        ],
    )


class MinimalRNASeqValidationError(ValueError):
    def __init__(
        self,
        errors: list[str],
        warnings: list[str] | None = None,
        *,
        error_code: str = "RNASEQ_INPUT_VALIDATION_FAILED",
        message: str = "RNA-seq input validation failed.",
    ) -> None:
        safe_errors = [error for error in errors if error]
        self.error_code = error_code
        self.message = message
        self.errors = safe_errors or [message]
        self.warnings = [warning for warning in warnings or [] if warning]
        super().__init__(message)

    def to_detail(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def build_validation_error(
    errors: list[str],
    warnings: list[str] | None = None,
) -> MinimalRNASeqValidationError:
    return MinimalRNASeqValidationError(
        errors=_unique_non_empty(errors),
        warnings=_unique_non_empty(warnings or []),
    )


def read_metadata(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file, delimiter=_delimiter_for_path(path))
        if reader.fieldnames is None:
            raise ValueError("Metadata file must include a header row.")

        reader.fieldnames = [_clean_cell(fieldname) for fieldname in reader.fieldnames]
        rows: list[dict] = []
        for row in reader:
            if row is None:
                continue
            normalized = {
                _clean_cell(key): _clean_cell(value)
                for key, value in row.items()
                if key is not None
            }
            if any(value for value in normalized.values()):
                rows.append(normalized)
        return rows


def read_count_matrix(path: Path) -> CountMatrix:
    with path.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.reader(input_file, delimiter=_delimiter_for_path(path))
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("Count matrix file must include a header row.") from exc

        header = [_clean_cell(cell) for cell in header]
        if not header:
            raise ValueError("Count matrix file must include a header row.")

        gene_id_column = header[0]
        sample_ids = header[1:]
        gene_ids: list[str] = []
        values: dict[str, dict[str, float]] = {}

        for line_number, row in enumerate(reader, start=2):
            if not row or all(not _clean_cell(cell) for cell in row):
                continue
            if len(row) < len(header):
                row = [*row, *([""] * (len(header) - len(row)))]
            if len(row) > len(header):
                raise ValueError(
                    f"Count matrix row {line_number} has more values than the header."
                )

            gene_id = _clean_cell(row[0])
            gene_ids.append(gene_id)
            row_values: dict[str, float] = {}
            for sample_id, raw_value in zip(sample_ids, row[1:]):
                value_text = _clean_cell(raw_value)
                if not value_text:
                    raise ValueError(
                        f"Count matrix row {line_number} contains an empty count value."
                    )
                try:
                    value = float(value_text)
                except ValueError as exc:
                    raise ValueError(
                        f"Count matrix row {line_number} contains a non-numeric count value."
                    ) from exc
                if not math.isfinite(value):
                    raise ValueError(
                        f"Count matrix row {line_number} contains a non-finite count value."
                    )
                row_values[sample_id] = value
            values[gene_id] = row_values

    return CountMatrix(
        gene_ids=gene_ids,
        sample_ids=sample_ids,
        values=values,
        gene_id_column=gene_id_column,
        raw_total_counts=_gene_totals(gene_ids, sample_ids, values),
    )


def normalize_metadata_rows(metadata: list[dict]) -> list[dict]:
    return [
        {
            _clean_cell(key): _clean_cell(value)
            for key, value in row.items()
            if key is not None
        }
        for row in metadata
    ]


def validate_metadata(metadata: list[dict]) -> ValidationResult:
    metadata = normalize_metadata_rows(metadata)
    errors: list[str] = []
    if not metadata:
        errors.append("Metadata must contain at least one sample row.")

    columns = set().union(*(row.keys() for row in metadata)) if metadata else set()
    for column in ("sample_id", "condition"):
        if column not in columns:
            errors.append(f"Metadata is missing required column: {column}.")

    sample_ids: list[str] = []
    for index, row in enumerate(metadata, start=1):
        sample_id = _clean_cell(row.get("sample_id"))
        condition = _clean_cell(row.get("condition"))
        if not sample_id:
            errors.append(f"Metadata row {index} has an empty sample_id.")
        if not condition:
            errors.append(f"Metadata row {index} has an empty condition.")
        sample_ids.append(sample_id)

    duplicates = _duplicates([sample_id for sample_id in sample_ids if sample_id])
    if duplicates:
        errors.append(f"Metadata contains duplicate sample_id values: {', '.join(duplicates)}.")

    non_empty_sample_ids = [sample_id for sample_id in sample_ids if sample_id]
    if len(set(non_empty_sample_ids)) < 2:
        errors.append("Metadata must contain at least 2 distinct samples.")

    condition_counts = _condition_counts(metadata)
    if len(condition_counts) < 2:
        errors.append(
            "Metadata must contain exactly 2 condition groups for preliminary log2 fold-change."
        )
    elif len(condition_counts) > 2:
        errors.append(
            "Metadata contains more than 2 condition groups; minimal RNA-seq supports exactly 2 condition groups."
        )

    return ValidationResult(
        valid=not errors,
        errors=errors,
        sample_count=len(non_empty_sample_ids),
        condition_counts=condition_counts,
    )


def validate_count_matrix(counts: CountMatrix) -> ValidationResult:
    errors: list[str] = []
    if counts.gene_id_column != "gene_id":
        errors.append("Count matrix first column must be gene_id.")
    if not counts.sample_ids:
        errors.append("Count matrix must contain at least one sample column.")
    if not counts.gene_ids:
        errors.append("Count matrix must contain at least one gene row.")

    empty_samples = [sample_id for sample_id in counts.sample_ids if not sample_id]
    if empty_samples:
        errors.append("Count matrix contains an empty sample ID column.")

    duplicate_samples = _duplicates([sample_id for sample_id in counts.sample_ids if sample_id])
    if duplicate_samples:
        errors.append(
            f"Count matrix contains duplicate sample columns: {', '.join(duplicate_samples)}."
        )

    empty_genes = [index for index, gene_id in enumerate(counts.gene_ids, start=1) if not gene_id]
    if empty_genes:
        errors.append("Count matrix contains an empty gene_id value.")

    duplicate_genes = _duplicates([gene_id for gene_id in counts.gene_ids if gene_id])
    if duplicate_genes:
        errors.append(f"Count matrix contains duplicate gene_id values: {', '.join(duplicate_genes)}.")

    for gene_id in counts.gene_ids:
        row = counts.values.get(gene_id, {})
        for sample_id in counts.sample_ids:
            value = row.get(sample_id)
            if value is None:
                errors.append(f"Count matrix is missing a value for gene {gene_id}.")
                continue
            if not math.isfinite(value):
                errors.append(f"Count matrix has a non-finite value for gene {gene_id}.")
            elif value < 0:
                errors.append(f"Count matrix has a negative count for gene {gene_id}.")
            elif not float(value).is_integer():
                errors.append(f"Count matrix has a non-integer count for gene {gene_id}.")

    if counts.sample_ids and counts.gene_ids:
        library_sizes = {sample_id: 0.0 for sample_id in counts.sample_ids}
        can_validate_library_sizes = True
        for gene_id in counts.gene_ids:
            row = counts.values.get(gene_id, {})
            for sample_id in counts.sample_ids:
                value = row.get(sample_id)
                if value is None or not math.isfinite(value) or value < 0:
                    can_validate_library_sizes = False
                    continue
                library_sizes[sample_id] += value
        if can_validate_library_sizes:
            zero_library_samples = [
                sample_id
                for sample_id, library_size in library_sizes.items()
                if sample_id and library_size == 0
            ]
            if zero_library_samples:
                errors.append(
                    "Count matrix contains zero library size samples: "
                    + ", ".join(zero_library_samples)
                    + "."
                )

    return ValidationResult(
        valid=not errors,
        errors=errors,
        sample_count=len([sample_id for sample_id in counts.sample_ids if sample_id]),
        gene_count=len([gene_id for gene_id in counts.gene_ids if gene_id]),
    )


def validate_sample_alignment(metadata: list[dict], counts: CountMatrix) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    metadata_sample_ids = [_clean_cell(row.get("sample_id")) for row in normalize_metadata_rows(metadata)]
    metadata_sample_ids = [sample_id for sample_id in metadata_sample_ids if sample_id]

    metadata_samples = set(metadata_sample_ids)
    count_sample_ids = [_clean_cell(sample_id) for sample_id in counts.sample_ids]
    count_sample_ids = [sample_id for sample_id in count_sample_ids if sample_id]
    count_samples = set(count_sample_ids)

    missing_from_counts = [
        sample_id for sample_id in metadata_sample_ids if sample_id not in count_samples
    ]
    extra_in_counts = [
        sample_id for sample_id in count_sample_ids if sample_id not in metadata_samples
    ]
    if missing_from_counts:
        errors.append(
            "Metadata sample IDs missing from count matrix: "
            + ", ".join(missing_from_counts)
            + "."
        )
    if extra_in_counts:
        errors.append(
            "Count matrix sample IDs missing from metadata: "
            + ", ".join(extra_in_counts)
            + "."
        )

    if not errors and metadata_sample_ids != count_sample_ids:
        warnings.append("Metadata sample order differs from count matrix; samples were matched by ID.")

    return ValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        sample_count=len(metadata_sample_ids),
    )


def validate_minimal_inputs(metadata: list[dict], counts: CountMatrix) -> ValidationResult:
    metadata_result = validate_metadata(metadata)
    count_result = validate_count_matrix(counts)
    alignment_result = validate_sample_alignment(metadata, counts)
    errors = [
        error
        for result in (metadata_result, count_result, alignment_result)
        for error in result.errors
    ]
    warnings = [
        warning
        for result in (metadata_result, count_result, alignment_result)
        for warning in result.warnings
    ]
    return ValidationResult(
        valid=not errors,
        errors=_unique_non_empty(errors),
        warnings=_unique_non_empty(warnings),
        sample_count=metadata_result.sample_count,
        gene_count=count_result.gene_count,
        condition_counts=dict(metadata_result.condition_counts),
    )


def reorder_counts_to_metadata(metadata: list[dict], counts: CountMatrix) -> CountMatrix:
    metadata_sample_ids = [
        _clean_cell(row.get("sample_id"))
        for row in normalize_metadata_rows(metadata)
        if _clean_cell(row.get("sample_id"))
    ]
    if metadata_sample_ids == counts.sample_ids:
        return counts

    if set(metadata_sample_ids) != set(counts.sample_ids):
        raise ValueError("Count matrix samples cannot be reordered because sample IDs do not align.")

    reordered_values = {
        gene_id: {
            sample_id: counts.values[gene_id][sample_id]
            for sample_id in metadata_sample_ids
        }
        for gene_id in counts.gene_ids
    }
    return CountMatrix(
        gene_ids=list(counts.gene_ids),
        sample_ids=list(metadata_sample_ids),
        values=reordered_values,
        gene_id_column=counts.gene_id_column,
        raw_total_counts=_gene_totals(counts.gene_ids, metadata_sample_ids, reordered_values),
    )


def compute_library_sizes(counts: CountMatrix) -> dict:
    library_sizes = {sample_id: 0.0 for sample_id in counts.sample_ids}
    for gene_id in counts.gene_ids:
        row = counts.values[gene_id]
        for sample_id in counts.sample_ids:
            library_sizes[sample_id] += row[sample_id]
    return library_sizes


def compute_cpm(counts: CountMatrix) -> CountMatrix:
    library_sizes = compute_library_sizes(counts)
    cpm_values: dict[str, dict[str, float]] = {}
    for gene_id in counts.gene_ids:
        cpm_values[gene_id] = {}
        for sample_id in counts.sample_ids:
            library_size = library_sizes[sample_id]
            cpm_values[gene_id][sample_id] = (
                counts.values[gene_id][sample_id] / library_size * 1_000_000.0
                if library_size > 0
                else 0.0
            )
    return CountMatrix(
        gene_ids=list(counts.gene_ids),
        sample_ids=list(counts.sample_ids),
        values=cpm_values,
        raw_total_counts=_gene_totals(counts.gene_ids, counts.sample_ids, counts.values),
    )


def filter_low_expression(counts: CountMatrix, min_total_count: int = 10) -> CountMatrix:
    retained_gene_ids = [
        gene_id
        for gene_id in counts.gene_ids
        if _raw_total_for_gene(counts, gene_id) >= min_total_count
    ]
    return CountMatrix(
        gene_ids=retained_gene_ids,
        sample_ids=list(counts.sample_ids),
        values={
            gene_id: dict(counts.values[gene_id])
            for gene_id in retained_gene_ids
        },
        gene_id_column=counts.gene_id_column,
        raw_total_counts={
            gene_id: _raw_total_for_gene(counts, gene_id)
            for gene_id in retained_gene_ids
        },
    )


def compute_preliminary_log2fc(
    counts_or_cpm: CountMatrix,
    metadata: list[dict],
    contrast: ContrastSpec | None = None,
) -> list[dict]:
    resolved_contrast = contrast or resolve_contrast(metadata)
    condition_order = _condition_order(metadata)
    if len(condition_order) != 2:
        raise ValueError(
            "Preliminary log2 fold-change ranking requires exactly two condition groups."
        )

    denominator = resolved_contrast.contrast_denominator
    numerator = resolved_contrast.contrast_numerator
    samples_by_group = {
        group: [
            _clean_cell(row.get("sample_id"))
            for row in metadata
            if _clean_cell(row.get("condition")) == group
            and _clean_cell(row.get("sample_id")) in counts_or_cpm.sample_ids
        ]
        for group in (denominator, numerator)
    }

    if not samples_by_group[denominator] or not samples_by_group[numerator]:
        raise ValueError("Each condition group must have at least one aligned sample.")

    rows: list[dict] = []
    contrast_payload = resolved_contrast.as_dict()
    note = (
        "Preliminary ranking only; contrast="
        f"{contrast_payload['direction']}; "
        "group_1 is the denominator and group_2 is the numerator; "
        "log2 fold change uses log2(mean CPM numerator + 1) - "
        "log2(mean CPM denominator + 1); "
        "no formal differential expression statistical test was performed."
    )
    for gene_id in counts_or_cpm.gene_ids:
        row = counts_or_cpm.values[gene_id]
        mean_group_1 = _mean(row[sample_id] for sample_id in samples_by_group[denominator])
        mean_group_2 = _mean(row[sample_id] for sample_id in samples_by_group[numerator])
        log2_fold_change = math.log2(mean_group_2 + 1.0) - math.log2(mean_group_1 + 1.0)
        rows.append(
            {
                "gene_id": gene_id,
                "mean_cpm_group_1": mean_group_1,
                "mean_cpm_group_2": mean_group_2,
                "log2_fold_change": log2_fold_change,
                "total_count": _raw_total_for_gene(counts_or_cpm, gene_id),
                "analysis_method": MINIMAL_ANALYSIS_METHOD,
                "formal_statistical_test": False,
                "pvalue_available": False,
                "adjusted_pvalue_available": False,
                "contrast_column": contrast_payload["contrast_column"],
                "contrast_numerator": contrast_payload["contrast_numerator"],
                "contrast_denominator": contrast_payload["contrast_denominator"],
                "contrast_direction": contrast_payload["direction"],
                "positive_log2fc_interpretation": contrast_payload[
                    "positive_log2fc_interpretation"
                ],
                "negative_log2fc_interpretation": contrast_payload[
                    "negative_log2fc_interpretation"
                ],
                "analysis_note": note,
            }
        )

    return sorted(
        rows,
        key=lambda row: (-abs(float(row["log2_fold_change"])), str(row["gene_id"])),
    )


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({fieldname: _format_value(row.get(fieldname, "")) for fieldname in fieldnames})


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_report_payload(
    *,
    task_id: str,
    execution_mode: str,
    metadata_file: str,
    count_matrix_file: str,
    sample_count: int,
    gene_count: int,
    retained_gene_count_after_filtering: int,
    condition_counts: dict,
    library_sizes: dict,
    min_total_count_filter: int,
    generated_files: list[dict] | None = None,
    preliminary_rows: list[dict] | None = None,
    contrast: dict | None = None,
) -> dict:
    method_contract = get_minimal_method_contract()
    return {
        "task_id": str(task_id),
        "execution_mode": str(execution_mode),
        "analysis_method": method_contract["analysis_method"],
        "analysis_method_display_name": method_contract["analysis_method_display_name"],
        "formal_de_method": method_contract["formal_de_method"],
        "formal_de_ready": method_contract["formal_de_ready"],
        "statistical_test_performed": method_contract["statistical_test_performed"],
        "pvalue_available": method_contract["pvalue_available"],
        "adjusted_pvalue_available": method_contract["adjusted_pvalue_available"],
        "external_tools_called": method_contract["external_tools_called"],
        "method_limitations": list(method_contract["method_limitations"]),
        "next_supported_formal_methods": list(method_contract["next_supported_formal_methods"]),
        "metadata_file": _safe_relative_path(metadata_file),
        "count_matrix_file": _safe_relative_path(count_matrix_file),
        "sample_count": int(sample_count),
        "gene_count": int(gene_count),
        "retained_gene_count_after_filtering": int(retained_gene_count_after_filtering),
        "condition_counts": _normalized_condition_counts(condition_counts),
        "library_sizes": _normalized_library_sizes(library_sizes),
        "min_total_count_filter": int(min_total_count_filter),
        "contrast": _normalized_contrast(contrast),
        "generated_artifacts": _report_generated_artifacts(generated_files or []),
        "top_preliminary_ranked_genes": summarize_top_ranked_genes(preliminary_rows or []),
        "limitations": _default_report_limitations(),
    }


def summarize_top_ranked_genes(rows: list[dict], limit: int = 5) -> list[dict]:
    if limit <= 0:
        return []

    ranked_rows = sorted(
        rows,
        key=lambda row: (
            -abs(_safe_float(row.get("log2_fold_change"))),
            str(row.get("gene_id", "")),
        ),
    )
    return [
        {
            "gene_id": str(row.get("gene_id", "")),
            "mean_cpm_group_1": _format_decimal(
                row.get("mean_cpm_group_1", 0.0),
                _CPM_DECIMAL_PLACES,
            ),
            "mean_cpm_group_2": _format_decimal(
                row.get("mean_cpm_group_2", 0.0),
                _CPM_DECIMAL_PLACES,
            ),
            "log2_fold_change": _format_decimal(
                row.get("log2_fold_change", 0.0),
                _LOG2FC_DECIMAL_PLACES,
            ),
            "total_count": _format_count_number(row.get("total_count", 0.0)),
        }
        for row in ranked_rows[:limit]
    ]


def format_markdown_table(columns: list[str], rows: list[dict]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = [
        "| "
        + " | ".join(_format_markdown_cell(row.get(column, "")) for column in columns)
        + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def write_markdown_report(path: Path, payload: dict) -> None:
    payload = _normalize_report_payload(payload)
    generated_artifacts = payload["generated_artifacts"]
    top_ranked_genes = payload["top_preliminary_ranked_genes"]
    contrast = payload["contrast"]
    library_size_rows = [
        {"sample_id": sample_id, "library_size": _format_count_number(library_size)}
        for sample_id, library_size in payload["library_sizes"].items()
    ]
    condition_count_rows = [
        {"condition": condition, "sample_count": sample_count}
        for condition, sample_count in payload["condition_counts"].items()
    ]

    lines = [
        "# Minimal Bulk RNA-seq MVP Report",
        "",
        "## Analysis summary",
        "",
        f"- task_id: `{payload['task_id']}`",
        f"- Execution mode: `{payload['execution_mode']}`",
        f"- Metadata file: `{payload['metadata_file']}`",
        f"- Count matrix file: `{payload['count_matrix_file']}`",
        f"- Sample count: {payload['sample_count']}",
        f"- Gene count: {payload['gene_count']}",
        (
            "- Retained gene count after filtering: "
            f"{payload['retained_gene_count_after_filtering']}"
        ),
        f"- Condition groups: {_format_condition_counts(payload['condition_counts'])}",
        "- Generated artifacts: "
        + ", ".join(f"`{artifact['name']}`" for artifact in generated_artifacts),
        "",
        "## Analysis method contract",
        "",
        f"- Current method: `{payload['analysis_method']}`",
        f"- Formal DE method: {_format_formal_de_method(payload['formal_de_method'])}",
        (
            "- Statistical test performed: "
            f"{_format_bool(payload['statistical_test_performed'])}"
        ),
        f"- P-values available: {_format_bool(payload['pvalue_available'])}",
        (
            "- Adjusted p-values available: "
            f"{_format_bool(payload['adjusted_pvalue_available'])}"
        ),
        (
            "- Future formal methods planned: "
            f"{_format_supported_formal_methods(payload['next_supported_formal_methods'])}"
        ),
        "",
        "## Input validation summary",
        "",
        f"- Metadata file was validated: `{payload['metadata_file']}`",
        f"- Count matrix file was validated: `{payload['count_matrix_file']}`",
        "- Sample IDs were aligned between metadata and count matrix.",
        "- Required metadata columns (`sample_id`, `condition`) and count matrix first column (`gene_id`) were present.",
        "- No formal statistical model was fitted.",
        "",
        "## QC summary",
        "",
        f"- Sample count: {payload['sample_count']}",
        f"- Gene count: {payload['gene_count']}",
        (
            "- Retained gene count after filtering: "
            f"{payload['retained_gene_count_after_filtering']}"
        ),
        f"- Low-expression filter threshold: total count >= {payload['min_total_count_filter']}",
        "",
        "Library sizes per sample:",
        "",
        format_markdown_table(["sample_id", "library_size"], library_size_rows),
        "",
        "Condition counts:",
        "",
        format_markdown_table(["condition", "sample_count"], condition_count_rows),
        "",
        "## Normalization summary",
        "",
        "- CPM normalization was computed.",
        "- CPM is library-size normalization: counts are scaled by each sample library size to counts per million.",
        "- CPM does not replace formal differential expression modeling.",
        "",
        "## Preliminary log2 fold-change ranking",
        "",
        "- Ranking is based on group-level mean CPM comparison.",
        "- Exactly two conditions are supported.",
        "- No formal statistical test was performed.",
        "- No p-values or adjusted p-values are reported.",
        "- Users should not label this table as a final DEG list.",
        "",
        "## Contrast direction",
        "",
        f"- Contrast source: `{contrast['contrast_source']}`",
        f"- Contrast column: `{contrast['contrast_column']}`",
        f"- Direction: `{contrast['direction']}`",
        (
            "- Positive log2 fold change: "
            f"{contrast['positive_log2fc_interpretation']}"
        ),
        (
            "- Negative log2 fold change: "
            f"{contrast['negative_log2fc_interpretation']}"
        ),
        (
            "- Formula: log2(mean CPM of "
            f"{contrast['contrast_numerator']} + 1) - log2(mean CPM of "
            f"{contrast['contrast_denominator']} + 1)."
        ),
        "",
        "## Top preliminary ranked genes",
        "",
        *(
            format_markdown_table(_TOP_RANKED_GENE_COLUMNS, top_ranked_genes).splitlines()
            if top_ranked_genes
            else ["No preliminary ranked genes were available after filtering."]
        ),
        "",
        "## Generated artifacts",
        "",
        *[
            f"- `{artifact['name']}`: `{artifact['relative_path']}`"
            for artifact in generated_artifacts
        ],
        "",
        "## Limitations",
        "",
        *[f"- {limitation}" for limitation in payload["limitations"]],
        "",
        "## Recommended next steps",
        "",
        "- Verify the sample metadata design.",
        "- Inspect QC metrics before interpreting the ranking.",
        "- Proceed to formal DESeq2, edgeR, or limma analysis in future phases.",
        "- Consider biological replicates and batch design before formal statistics.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _normalize_report_payload(payload: dict) -> dict:
    method_contract = get_minimal_method_contract()
    return {
        "task_id": str(payload.get("task_id", "unknown")),
        "execution_mode": str(payload.get("execution_mode", "minimal_real")),
        "analysis_method": str(
            payload.get("analysis_method") or method_contract["analysis_method"]
        ),
        "analysis_method_display_name": str(
            payload.get("analysis_method_display_name")
            or method_contract["analysis_method_display_name"]
        ),
        "formal_de_method": payload.get("formal_de_method"),
        "formal_de_ready": bool(
            payload.get("formal_de_ready", method_contract["formal_de_ready"])
        ),
        "statistical_test_performed": bool(
            payload.get(
                "statistical_test_performed",
                method_contract["statistical_test_performed"],
            )
        ),
        "pvalue_available": bool(
            payload.get("pvalue_available", method_contract["pvalue_available"])
        ),
        "adjusted_pvalue_available": bool(
            payload.get(
                "adjusted_pvalue_available",
                method_contract["adjusted_pvalue_available"],
            )
        ),
        "external_tools_called": bool(
            payload.get("external_tools_called", method_contract["external_tools_called"])
        ),
        "method_limitations": payload.get("method_limitations")
        or list(method_contract["method_limitations"]),
        "next_supported_formal_methods": payload.get("next_supported_formal_methods")
        or list(method_contract["next_supported_formal_methods"]),
        "metadata_file": _safe_relative_path(payload.get("metadata_file", "metadata.csv")),
        "count_matrix_file": _safe_relative_path(
            payload.get("count_matrix_file", "counts.csv")
        ),
        "sample_count": int(payload.get("sample_count", 0)),
        "gene_count": int(payload.get("gene_count", 0)),
        "retained_gene_count_after_filtering": int(
            payload.get("retained_gene_count_after_filtering", 0)
        ),
        "condition_counts": _normalized_condition_counts(
            payload.get("condition_counts", {})
        ),
        "library_sizes": _normalized_library_sizes(payload.get("library_sizes", {})),
        "min_total_count_filter": int(payload.get("min_total_count_filter", 0)),
        "contrast": _normalized_contrast(payload.get("contrast")),
        "generated_artifacts": payload.get("generated_artifacts")
        or _report_generated_artifacts(payload.get("generated_files", [])),
        "top_preliminary_ranked_genes": payload.get("top_preliminary_ranked_genes")
        or summarize_top_ranked_genes(payload.get("preliminary_rows", [])),
        "limitations": payload.get("limitations") or _default_report_limitations(),
    }


def _report_generated_artifacts(generated_files: list[dict]) -> list[dict]:
    entries_by_name = {
        str(entry.get("name", "")): entry
        for entry in generated_files
        if str(entry.get("name", "")) in _REPORT_ARTIFACTS
    }
    artifacts: list[dict] = []
    for artifact_name in _REPORT_ARTIFACTS:
        entry = entries_by_name.get(artifact_name, {})
        artifacts.append(
            {
                "name": artifact_name,
                "relative_path": _safe_relative_path(
                    entry.get("relative_path") or artifact_name
                ),
            }
        )
    return artifacts


def _default_report_limitations() -> list[str]:
    return [
        "No DESeq2, edgeR, or limma was run.",
        "No statistical test was performed.",
        "No p-values or adjusted p-values are available.",
        "No batch correction was performed.",
        "No GO/KEGG gene-set analysis was performed.",
        "Preliminary log2FC ranking is exploratory only.",
        "Results are not suitable for publication-level differential expression claims.",
    ]


def _normalized_condition_counts(condition_counts: dict) -> dict[str, int]:
    return {
        str(condition): int(count)
        for condition, count in condition_counts.items()
    }


def _normalized_library_sizes(library_sizes: dict) -> dict[str, float]:
    return {
        str(sample_id): _safe_float(library_size)
        for sample_id, library_size in library_sizes.items()
    }


def _normalized_contrast(contrast: object) -> dict:
    if not isinstance(contrast, dict):
        return {
            "contrast_column": "condition",
            "contrast_numerator": "group_2",
            "contrast_denominator": "group_1",
            "direction": "group_2_vs_group_1",
            "positive_log2fc_interpretation": "Higher in group_2 relative to group_1",
            "negative_log2fc_interpretation": "Lower in group_2 relative to group_1",
            "contrast_source": "unspecified",
            "inferred": False,
        }

    numerator = str(contrast.get("contrast_numerator") or "group_2")
    denominator = str(contrast.get("contrast_denominator") or "group_1")
    return {
        "contrast_column": str(contrast.get("contrast_column") or "condition"),
        "contrast_numerator": numerator,
        "contrast_denominator": denominator,
        "direction": str(
            contrast.get("direction") or f"{numerator}_vs_{denominator}"
        ),
        "positive_log2fc_interpretation": str(
            contrast.get("positive_log2fc_interpretation")
            or f"Higher in {numerator} relative to {denominator}"
        ),
        "negative_log2fc_interpretation": str(
            contrast.get("negative_log2fc_interpretation")
            or f"Lower in {numerator} relative to {denominator}"
        ),
        "contrast_source": str(contrast.get("contrast_source") or "unspecified"),
        "inferred": bool(contrast.get("inferred", False)),
    }


def _format_condition_counts(condition_counts: dict[str, int]) -> str:
    if not condition_counts:
        return "none"
    return ", ".join(
        f"{condition}={sample_count}"
        for condition, sample_count in condition_counts.items()
    )


def _format_bool(value: object) -> str:
    return "true" if bool(value) else "false"


def _format_formal_de_method(value: object) -> str:
    normalized_method = _normalize_method_name(value)
    if not normalized_method:
        return "not run"
    return _FORMAL_METHOD_DISPLAY_NAMES.get(normalized_method, normalized_method)


def _format_supported_formal_methods(methods: object) -> str:
    if not isinstance(methods, list):
        methods = get_supported_formal_methods()
    display_names = [
        _FORMAL_METHOD_DISPLAY_NAMES.get(_normalize_method_name(method), str(method))
        for method in methods
        if _normalize_method_name(method)
    ]
    return ", ".join(display_names) if display_names else "none"


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


def _format_markdown_cell(value: object) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def _safe_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _format_decimal(value: object, decimal_places: int) -> str:
    number = _safe_float(value)
    if abs(number) < 0.5 * (10 ** -decimal_places):
        number = 0.0
    return f"{number:.{decimal_places}f}"


def _format_count_number(value: object) -> str:
    number = _safe_float(value)
    if number.is_integer():
        return str(int(number))
    return _format_decimal(number, _CPM_DECIMAL_PLACES)


def _delimiter_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return ","
    if suffix == ".tsv":
        return "\t"
    if suffix == ".txt":
        sample = path.read_text(encoding="utf-8", errors="ignore")[:4096]
        if "\t" in sample:
            return "\t"
        if "," in sample:
            return ","
    return "\t"


def _clean_cell(value: object) -> str:
    return "" if value is None else str(value).strip()


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _unique_non_empty(values: list[str]) -> list[str]:
    return _unique_preserving_first_seen([value for value in values if value])


def _unique_preserving_first_seen(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value not in seen:
            unique_values.append(value)
            seen.add(value)
    return unique_values


def _normalize_method_name(method: object) -> str:
    return "" if method is None else str(method).strip().lower()


def _safe_public_method_name(method: object) -> str:
    normalized_method = _normalize_method_name(method)
    if normalized_method in {MINIMAL_ANALYSIS_METHOD, *_SUPPORTED_FUTURE_FORMAL_METHODS}:
        return normalized_method
    return "unsupported"


def _gene_totals(
    gene_ids: list[str],
    sample_ids: list[str],
    values: dict[str, dict[str, float]],
) -> dict[str, float]:
    return {
        gene_id: sum(values.get(gene_id, {}).get(sample_id, 0.0) for sample_id in sample_ids)
        for gene_id in gene_ids
    }


def _raw_total_for_gene(counts: CountMatrix, gene_id: str) -> float:
    if gene_id in counts.raw_total_counts:
        return counts.raw_total_counts[gene_id]
    return sum(counts.values[gene_id][sample_id] for sample_id in counts.sample_ids)


def _condition_order(metadata: list[dict]) -> list[str]:
    conditions: list[str] = []
    for row in metadata:
        condition = _clean_cell(row.get("condition"))
        if condition and condition not in conditions:
            conditions.append(condition)
    return conditions


def _condition_counts(metadata: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in metadata:
        condition = _clean_cell(row.get("condition"))
        if condition:
            counts[condition] = counts.get(condition, 0) + 1
    return counts


def _mean(values: object) -> float:
    collected = list(values)
    return sum(collected) / len(collected) if collected else 0.0


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return str(int(value))
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)
