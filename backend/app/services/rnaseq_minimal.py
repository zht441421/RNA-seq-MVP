import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path


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


def compute_preliminary_log2fc(counts_or_cpm: CountMatrix, metadata: list[dict]) -> list[dict]:
    condition_order = _condition_order(metadata)
    if len(condition_order) != 2:
        raise ValueError(
            "Preliminary log2 fold-change ranking requires exactly two condition groups."
        )

    group_1, group_2 = condition_order
    samples_by_group = {
        group: [
            _clean_cell(row.get("sample_id"))
            for row in metadata
            if _clean_cell(row.get("condition")) == group
            and _clean_cell(row.get("sample_id")) in counts_or_cpm.sample_ids
        ]
        for group in condition_order
    }

    if not samples_by_group[group_1] or not samples_by_group[group_2]:
        raise ValueError("Each condition group must have at least one aligned sample.")

    rows: list[dict] = []
    note = (
        "Preliminary ranking only; group_1="
        f"{group_1}; group_2={group_2}; "
        "log2 fold change uses group mean CPM with a +1 CPM pseudocount; "
        "no formal differential expression statistical test was performed."
    )
    for gene_id in counts_or_cpm.gene_ids:
        row = counts_or_cpm.values[gene_id]
        mean_group_1 = _mean(row[sample_id] for sample_id in samples_by_group[group_1])
        mean_group_2 = _mean(row[sample_id] for sample_id in samples_by_group[group_2])
        log2_fold_change = math.log2((mean_group_2 + 1.0) / (mean_group_1 + 1.0))
        rows.append(
            {
                "gene_id": gene_id,
                "mean_cpm_group_1": mean_group_1,
                "mean_cpm_group_2": mean_group_2,
                "log2_fold_change": log2_fold_change,
                "total_count": _raw_total_for_gene(counts_or_cpm, gene_id),
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


def write_markdown_report(path: Path, payload: dict) -> None:
    lines = [
        "# Minimal Bulk RNA-seq MVP Analysis",
        "",
        "This is a minimal Bulk RNA-seq MVP analysis.",
        "",
        "CPM normalization and preliminary log2 fold-change ranking were computed.",
        "",
        "No formal differential expression statistical test was performed.",
        "",
        "No p-values or adjusted p-values are reported.",
        "",
        "Results are not a substitute for DESeq2/edgeR/limma.",
        "",
        "## Inputs",
        "",
        f"- Metadata file: `{payload['metadata_file']}`",
        f"- Count matrix file: `{payload['count_matrix_file']}`",
        "",
        "## QC Summary",
        "",
        f"- Samples: {payload['sample_count']}",
        f"- Genes: {payload['gene_count']}",
        f"- Genes retained after low-count filter: {payload['retained_gene_count_after_filtering']}",
        f"- Minimum total count filter: {payload['min_total_count_filter']}",
        "",
        "## Limitations",
        "",
        *[f"- {limitation}" for limitation in payload["limitations"]],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


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
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return str(int(value))
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)
