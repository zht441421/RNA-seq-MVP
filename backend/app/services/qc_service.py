from statistics import mean, median
from typing import Any, Dict, List, Optional

from backend.app.config import get_settings
from backend.app.models.qc_report import (
    BatchGroupAssessment,
    LibrarySizeSummary,
    LowCountGeneSummary,
    QCCheck,
    QCReport,
    QCSeverity,
    QCStatus,
    SampleAlignment,
    ValidationIssue,
)
from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.services.file_inspector import inspect_file, iter_table_rows, read_table_records


def run_qc(config: BulkRNASeqAnalysisConfig) -> QCReport:
    checks: List[QCCheck] = []
    group_counts: Dict[str, int] = {}
    sample_alignment: Optional[SampleAlignment] = None
    library_size_summary: Optional[LibrarySizeSummary] = None
    low_count_gene_summary: Optional[LowCountGeneSummary] = None
    batch_group_assessment: Optional[BatchGroupAssessment] = None

    try:
        count_inspection = inspect_file(config.count_matrix_file)
        checks.append(_check("count_matrix_readable", QCStatus.PASS, QCSeverity.INFO, "Count matrix is readable."))
    except Exception as exc:
        checks.append(
            _check(
                "count_matrix_readable",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Count matrix file is missing or cannot be read.",
                {"path": config.count_matrix_file, "error": str(exc)},
            )
        )
        return _report(config.project_id, checks)

    try:
        metadata_inspection = inspect_file(config.metadata_file)
        metadata_rows = read_table_records(config.metadata_file)
        checks.append(_check("metadata_readable", QCStatus.PASS, QCSeverity.INFO, "Metadata table is readable."))
    except Exception as exc:
        checks.append(
            _check(
                "metadata_readable",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Metadata file is missing or cannot be read.",
                {"path": config.metadata_file, "error": str(exc)},
            )
        )
        return _report(config.project_id, checks)

    if metadata_inspection.row_count == 0:
        checks.append(
            _check(
                "metadata_has_sample_rows",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Metadata does not contain any sample rows.",
                {"metadata_file": config.metadata_file},
            )
        )

    if config.sample_id_column not in metadata_inspection.columns:
        checks.append(
            _check(
                "sample_id_column_present",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                f"Sample ID column '{config.sample_id_column}' is missing from metadata.",
            )
        )
        return _report(config.project_id, checks)
    checks.append(_check("sample_id_column_present", QCStatus.PASS, QCSeverity.INFO, "Sample ID column is present."))

    if config.gene_id_column not in count_inspection.columns:
        checks.append(
            _check(
                "gene_id_column_present",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                f"Gene ID column '{config.gene_id_column}' is missing from count matrix.",
            )
        )
        return _report(config.project_id, checks)
    checks.append(_check("gene_id_column_present", QCStatus.PASS, QCSeverity.INFO, "Gene ID column is present."))

    metadata_sample_ids = [str(row.get(config.sample_id_column, "")).strip() for row in metadata_rows]
    metadata_sample_ids = [sample_id for sample_id in metadata_sample_ids if sample_id]
    matrix_sample_columns = [column for column in count_inspection.columns if column != config.gene_id_column]
    if not matrix_sample_columns:
        checks.append(
            _check(
                "count_matrix_has_sample_columns",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Count matrix does not contain any sample count columns.",
                {"columns": count_inspection.columns, "gene_id_column": config.gene_id_column},
            )
        )
    if not metadata_sample_ids:
        checks.append(
            _check(
                "metadata_has_sample_ids",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Metadata does not contain usable sample IDs.",
                {"sample_id_column": config.sample_id_column},
            )
        )
    missing_in_metadata = sorted(set(matrix_sample_columns) - set(metadata_sample_ids))
    missing_in_count_matrix = sorted(set(metadata_sample_ids) - set(matrix_sample_columns))
    sample_alignment = SampleAlignment(
        metadata_sample_count=len(metadata_sample_ids),
        matrix_sample_count=len(matrix_sample_columns),
        matched_sample_count=len(set(metadata_sample_ids).intersection(matrix_sample_columns)),
        missing_in_metadata=missing_in_metadata,
        missing_in_count_matrix=missing_in_count_matrix,
        ordered_match=metadata_sample_ids == matrix_sample_columns,
    )
    if missing_in_metadata or missing_in_count_matrix:
        checks.append(
            _check(
                "sample_ids_aligned",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Sample IDs do not align between metadata and count matrix.",
                _model_to_dict(sample_alignment),
            )
        )
    else:
        checks.append(
            _check(
                "sample_ids_aligned",
                QCStatus.PASS,
                QCSeverity.INFO,
                "Sample IDs align between metadata and count matrix.",
                _model_to_dict(sample_alignment),
            )
        )

    duplicate_samples = sorted(_duplicates(metadata_sample_ids))
    if duplicate_samples:
        checks.append(
            _check(
                "metadata_sample_ids_unique",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Metadata sample IDs must be unique.",
                {"duplicates": duplicate_samples},
            )
        )
    else:
        checks.append(_check("metadata_sample_ids_unique", QCStatus.PASS, QCSeverity.INFO, "Metadata sample IDs are unique."))

    if config.group_column not in metadata_inspection.columns:
        checks.append(
            _check(
                "group_column_present",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                f"Group column '{config.group_column}' is missing from metadata.",
            )
        )
    else:
        missing_group_rows = [
            str(row.get(config.sample_id_column, "")).strip()
            for row in metadata_rows
            if not str(row.get(config.group_column, "")).strip()
        ]
        if missing_group_rows:
            checks.append(
                _check(
                    "group_values_complete",
                    QCStatus.FAIL,
                    QCSeverity.ERROR,
                    "Group column contains missing values.",
                    {
                        "group_column": config.group_column,
                        "samples_with_missing_group": [sample for sample in missing_group_rows if sample],
                        "missing_group_row_count": len(missing_group_rows),
                    },
                )
            )
        else:
            checks.append(_check("group_values_complete", QCStatus.PASS, QCSeverity.INFO, "Group values are complete."))

        group_counts = _count_groups(metadata_rows, config.group_column)
        checks.append(
            _check(
                "group_column_present",
                QCStatus.PASS,
                QCSeverity.INFO,
                "Group column is present.",
                {"group_counts": group_counts},
            )
        )
        if len(group_counts) < 2:
            checks.append(
                _check(
                    "group_count_at_least_two",
                    QCStatus.FAIL,
                    QCSeverity.ERROR,
                    "Metadata must contain at least two groups for differential expression.",
                    {"group_counts": group_counts},
                )
            )
        _check_group_presence(checks, group_counts, config.reference_group, "reference_group_present")
        _check_group_presence(checks, group_counts, config.test_group, "test_group_present")
        for group_name, group_count in sorted(group_counts.items()):
            if group_count < 1:
                checks.append(
                    _check(
                        "group_sample_size",
                        QCStatus.FAIL,
                        QCSeverity.ERROR,
                        f"Group '{group_name}' has no samples.",
                        {"group": group_name, "n": group_count},
                    )
                )
            elif group_count < 2:
                checks.append(
                    _check(
                        "group_sample_size",
                        QCStatus.WARN,
                        QCSeverity.WARNING,
                        f"Group '{group_name}' has fewer than 2 samples.",
                        {"group": group_name, "n": group_count},
                    )
                )

    count_metrics = _scan_count_matrix(config.count_matrix_file, config.gene_id_column, matrix_sample_columns)
    if count_metrics["na_count_cells"] > 0:
        checks.append(
            _check(
                "count_values_not_missing",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Count matrix contains missing count values.",
                {"na_count_cells": count_metrics["na_count_cells"]},
            )
        )
    else:
        checks.append(_check("count_values_not_missing", QCStatus.PASS, QCSeverity.INFO, "Count values are not missing."))

    if count_metrics["non_numeric_count_cells"] > 0:
        checks.append(
            _check(
                "count_values_numeric",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Count matrix contains non-numeric count values.",
                {"non_numeric_count_cells": count_metrics["non_numeric_count_cells"]},
            )
        )
    else:
        checks.append(_check("count_values_numeric", QCStatus.PASS, QCSeverity.INFO, "Count values are numeric."))

    if count_metrics["negative_count_cells"] > 0:
        checks.append(
            _check(
                "count_values_non_negative",
                QCStatus.FAIL,
                QCSeverity.ERROR,
                "Count matrix contains negative count values.",
                {"negative_count_cells": count_metrics["negative_count_cells"]},
            )
        )
    else:
        checks.append(_check("count_values_non_negative", QCStatus.PASS, QCSeverity.INFO, "Count values are non-negative."))

    if count_metrics["non_integer_count_cells"] > 0:
        checks.append(
            _check(
                "count_values_integer_like",
                QCStatus.WARN,
                QCSeverity.WARNING,
                "Some count values are not integer-like.",
                {"non_integer_count_cells": count_metrics["non_integer_count_cells"]},
            )
        )
    else:
        checks.append(_check("count_values_integer_like", QCStatus.PASS, QCSeverity.INFO, "Count values are integer-like."))

    if count_metrics["duplicated_gene_ids"]:
        checks.append(
            _check(
                "gene_ids_unique",
                QCStatus.WARN,
                QCSeverity.WARNING,
                "Count matrix contains duplicated gene IDs.",
                {
                    "duplicate_gene_count": len(count_metrics["duplicated_gene_ids"]),
                    "duplicate_gene_examples": count_metrics["duplicated_gene_ids"][:10],
                },
            )
        )
    else:
        checks.append(_check("gene_ids_unique", QCStatus.PASS, QCSeverity.INFO, "Gene IDs are unique."))

    library_size_summary = _summarize_library_sizes(count_metrics["library_sizes"])
    if library_size_summary:
        checks.append(
            _check(
                "library_size_summary",
                QCStatus.INFO,
                QCSeverity.INFO,
                "Library size summary was computed.",
                _model_to_dict(library_size_summary),
            )
        )
        library_ratio = (
            float("inf")
            if library_size_summary.minimum == 0 and library_size_summary.maximum > 0
            else (
                library_size_summary.maximum / library_size_summary.minimum
                if library_size_summary.minimum > 0
                else 1
            )
        )
        if library_ratio > 4:
            checks.append(
                _check(
                    "library_size_balance",
                    QCStatus.WARN,
                    QCSeverity.WARNING,
                    "Library sizes are highly uneven.",
                    {"max_to_min_ratio": library_ratio},
                )
            )

    low_count_gene_summary = LowCountGeneSummary(
        total_genes=count_metrics["total_genes"],
        low_count_genes=count_metrics["low_count_genes"],
        low_count_fraction=(
            count_metrics["low_count_genes"] / count_metrics["total_genes"] if count_metrics["total_genes"] else 0.0
        ),
        min_total_count=get_settings().low_count_min_total,
    )
    checks.append(
        _check(
            "low_count_gene_summary",
            QCStatus.INFO,
            QCSeverity.INFO,
            "Low-count gene summary was computed.",
            _model_to_dict(low_count_gene_summary),
        )
    )

    if count_metrics["total_genes"] > 0:
        zero_gene_fraction = count_metrics["zero_count_genes"] / count_metrics["total_genes"]
        if zero_gene_fraction > 0.5:
            checks.append(
                _check(
                    "all_zero_gene_fraction",
                    QCStatus.WARN,
                    QCSeverity.WARNING,
                    "More than half of genes have zero total counts across all samples.",
                    {
                        "zero_count_genes": count_metrics["zero_count_genes"],
                        "total_genes": count_metrics["total_genes"],
                        "zero_gene_fraction": zero_gene_fraction,
                    },
                )
            )

    if config.batch_column:
        if config.batch_column not in metadata_inspection.columns:
            checks.append(
                _check(
                    "batch_column_present",
                    QCStatus.FAIL,
                    QCSeverity.ERROR,
                    f"Batch column '{config.batch_column}' is missing from metadata.",
                )
            )
        elif config.group_column in metadata_inspection.columns:
            batch_group_assessment = _assess_batch_group(metadata_rows, config.batch_column, config.group_column)
            if batch_group_assessment.is_potentially_confounding:
                checks.append(
                    _check(
                        "batch_group_confounding",
                        QCStatus.WARN,
                        QCSeverity.WARNING,
                        batch_group_assessment.message,
                        _model_to_dict(batch_group_assessment),
                    )
                )
            else:
                checks.append(
                    _check(
                        "batch_group_confounding",
                        QCStatus.PASS,
                        QCSeverity.INFO,
                        batch_group_assessment.message,
                        _model_to_dict(batch_group_assessment),
                    )
                )

    return QCReport(
        project_id=config.project_id,
        passed=not any(check.status == QCStatus.FAIL and check.severity == QCSeverity.ERROR for check in checks),
        checks=checks,
        validation_issues=_issues_from_checks(checks),
        group_counts=group_counts,
        sample_alignment=sample_alignment,
        library_size_summary=library_size_summary,
        low_count_gene_summary=low_count_gene_summary,
        batch_group_assessment=batch_group_assessment,
    )


def _report(project_id: str, checks: List[QCCheck]) -> QCReport:
    return QCReport(
        project_id=project_id,
        passed=not any(check.status == QCStatus.FAIL and check.severity == QCSeverity.ERROR for check in checks),
        checks=checks,
        validation_issues=_issues_from_checks(checks),
    )


def _check(name: str, status: QCStatus, severity: QCSeverity, message: str, details: Dict[str, Any] = None) -> QCCheck:
    return QCCheck(name=name, status=status, severity=severity, message=message, details=details or {})


def _check_group_presence(checks: List[QCCheck], group_counts: Dict[str, int], group_name: str, check_name: str) -> None:
    if group_name in group_counts and group_counts[group_name] > 0:
        checks.append(
            _check(check_name, QCStatus.PASS, QCSeverity.INFO, f"Group '{group_name}' exists.", {"n": group_counts[group_name]})
        )
    else:
        checks.append(
            _check(check_name, QCStatus.FAIL, QCSeverity.ERROR, f"Group '{group_name}' is absent.", {"n": 0})
        )


def _count_groups(rows: List[Dict[str, Any]], group_column: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        group = str(row.get(group_column, "")).strip()
        if not group:
            continue
        counts[group] = counts.get(group, 0) + 1
    return counts


def _scan_count_matrix(file_path: str, gene_id_column: str, sample_columns: List[str]) -> Dict[str, Any]:
    library_sizes = {sample: 0.0 for sample in sample_columns}
    total_genes = 0
    low_count_genes = 0
    zero_count_genes = 0
    invalid_count_cells = 0
    na_count_cells = 0
    non_numeric_count_cells = 0
    negative_count_cells = 0
    non_integer_count_cells = 0
    seen_gene_ids = set()
    duplicated_gene_ids = set()
    min_total_count = get_settings().low_count_min_total

    for row in iter_table_rows(file_path):
        total_genes += 1
        gene_id = str(row.get(gene_id_column, "")).strip()
        if gene_id:
            if gene_id in seen_gene_ids:
                duplicated_gene_ids.add(gene_id)
            seen_gene_ids.add(gene_id)
        gene_total = 0.0
        for sample in sample_columns:
            raw_value = row.get(sample)
            value_state = _classify_count_value(raw_value)
            if value_state == "missing":
                na_count_cells += 1
                invalid_count_cells += 1
                continue
            if value_state == "non_numeric":
                non_numeric_count_cells += 1
                invalid_count_cells += 1
                continue
            value = _parse_float(raw_value)
            if value is None:
                invalid_count_cells += 1
                continue
            if value < 0:
                negative_count_cells += 1
                continue
            if abs(value - round(value)) > 1e-6:
                non_integer_count_cells += 1
            library_sizes[sample] += value
            gene_total += value
        if gene_total < min_total_count:
            low_count_genes += 1
        if gene_total == 0:
            zero_count_genes += 1

    return {
        "gene_id_column": gene_id_column,
        "total_genes": total_genes,
        "low_count_genes": low_count_genes,
        "zero_count_genes": zero_count_genes,
        "library_sizes": library_sizes,
        "invalid_count_cells": invalid_count_cells,
        "na_count_cells": na_count_cells,
        "non_numeric_count_cells": non_numeric_count_cells,
        "negative_count_cells": negative_count_cells,
        "non_integer_count_cells": non_integer_count_cells,
        "duplicated_gene_ids": sorted(duplicated_gene_ids),
    }


def _classify_count_value(value: Any) -> str:
    if value is None:
        return "missing"
    text = str(value).strip()
    if text == "" or text.lower() in {"na", "nan", "null", "none"}:
        return "missing"
    try:
        float(text)
    except ValueError:
        return "non_numeric"
    return "numeric"


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _summarize_library_sizes(library_sizes: Dict[str, float]) -> Optional[LibrarySizeSummary]:
    if not library_sizes:
        return None
    values = list(library_sizes.values())
    return LibrarySizeSummary(
        sample_count=len(values),
        minimum=min(values),
        maximum=max(values),
        mean=mean(values),
        median=median(values),
        total_by_sample=library_sizes,
    )


def _assess_batch_group(rows: List[Dict[str, Any]], batch_column: str, group_column: str) -> BatchGroupAssessment:
    table: Dict[str, Dict[str, int]] = {}
    for row in rows:
        batch = str(row.get(batch_column, "")).strip()
        group = str(row.get(group_column, "")).strip()
        if not batch or not group:
            continue
        table.setdefault(batch, {})
        table[batch][group] = table[batch].get(group, 0) + 1

    all_batches_single_group = bool(table) and all(len(group_counts) == 1 for group_counts in table.values())
    group_to_batches: Dict[str, set[str]] = {}
    for batch, group_counts in table.items():
        for group in group_counts:
            group_to_batches.setdefault(group, set()).add(batch)
    groups_separated_by_batch = bool(group_to_batches) and all(len(batches) <= 1 for batches in group_to_batches.values())
    is_confounding = all_batches_single_group and groups_separated_by_batch
    message = (
        "Batch and group appear potentially confounded."
        if is_confounding
        else "No complete batch/group confounding detected by MVP rule."
    )
    return BatchGroupAssessment(
        batch_column=batch_column,
        is_potentially_confounding=is_confounding,
        table=table,
        message=message,
    )


def _duplicates(values: List[str]) -> List[str]:
    seen = set()
    duplicated = set()
    for value in values:
        if value in seen:
            duplicated.add(value)
        seen.add(value)
    return sorted(duplicated)


ISSUE_METADATA = {
    "count_matrix_readable": (
        "COUNT_MATRIX_UNREADABLE",
        "Check that the count matrix path is correct, the file exists, and the file type is csv, tsv, or xlsx.",
    ),
    "metadata_readable": (
        "METADATA_UNREADABLE",
        "Check that the metadata path is correct, the file exists, and the file type is csv, tsv, or xlsx.",
    ),
    "metadata_has_sample_rows": (
        "METADATA_EMPTY",
        "Add one metadata row for each biological sample.",
    ),
    "sample_id_column_present": (
        "SAMPLE_ID_COLUMN_MISSING",
        "Set sample_id_column to an existing metadata column that uniquely identifies samples.",
    ),
    "gene_id_column_present": (
        "GENE_ID_COLUMN_MISSING",
        "Set gene_id_column to an existing count matrix column containing gene identifiers.",
    ),
    "count_matrix_has_sample_columns": (
        "COUNT_MATRIX_NO_SAMPLE_COLUMNS",
        "Ensure the count matrix has one gene ID column plus at least one sample count column.",
    ),
    "metadata_has_sample_ids": (
        "METADATA_NO_SAMPLE_IDS",
        "Fill the metadata sample ID column with values that match count matrix sample columns.",
    ),
    "sample_ids_aligned": (
        "SAMPLE_ID_MISMATCH",
        "Ensure every sample column in the count matrix has exactly one matching row in metadata.",
    ),
    "metadata_sample_ids_unique": (
        "DUPLICATE_SAMPLE_IDS",
        "Remove duplicated sample_id values so each sample appears exactly once in metadata.",
    ),
    "group_column_present": (
        "GROUP_COLUMN_MISSING",
        "Set group_column to an existing metadata column describing the biological groups.",
    ),
    "group_values_complete": (
        "GROUP_VALUES_MISSING",
        "Fill missing group values or remove samples that should not be included in the contrast.",
    ),
    "group_count_at_least_two": (
        "GROUP_COUNT_TOO_LOW",
        "Provide at least two groups in metadata for differential expression.",
    ),
    "reference_group_present": (
        "REFERENCE_GROUP_MISSING",
        "Set reference_group to a value that exists in the group column.",
    ),
    "test_group_present": (
        "TEST_GROUP_MISSING",
        "Set test_group to a value that exists in the group column.",
    ),
    "group_sample_size": (
        "GROUP_SAMPLE_SIZE_LOW",
        "Use at least two biological replicates per group where possible.",
    ),
    "count_values_not_missing": (
        "COUNT_VALUES_MISSING",
        "Replace missing count cells with valid non-negative integer counts or remove affected genes/samples.",
    ),
    "count_values_numeric": (
        "COUNT_VALUES_NON_NUMERIC",
        "Ensure count cells contain numeric values only.",
    ),
    "count_values_non_negative": (
        "COUNT_VALUES_NEGATIVE",
        "Counts must be non-negative. Check preprocessing/export steps for invalid negative values.",
    ),
    "count_values_integer_like": (
        "COUNT_VALUES_NON_INTEGER",
        "Bulk RNA-seq count matrices should contain raw integer-like counts for DESeq2.",
    ),
    "gene_ids_unique": (
        "DUPLICATE_GENE_IDS",
        "Prefer unique gene IDs. Aggregate duplicated IDs or use a more specific identifier before analysis.",
    ),
    "library_size_balance": (
        "LIBRARY_SIZE_IMBALANCE",
        "Review samples with very small or very large library sizes before running differential expression.",
    ),
    "all_zero_gene_fraction": (
        "ALL_ZERO_GENE_FRACTION_HIGH",
        "Consider filtering unexpressed genes and confirming that count columns are correctly selected.",
    ),
    "batch_column_present": (
        "BATCH_COLUMN_MISSING",
        "Set batch_column to an existing metadata column or leave it empty if no batch variable should be modeled.",
    ),
    "batch_group_confounding": (
        "BATCH_GROUP_CONFOUNDING",
        "Review the study design. If batch and group are confounded, differential expression may not be interpretable.",
    ),
}


def _issues_from_checks(checks: List[QCCheck]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for check in checks:
        if not (
            (check.status == QCStatus.FAIL and check.severity == QCSeverity.ERROR)
            or check.status == QCStatus.WARN
            or check.severity == QCSeverity.WARNING
        ):
            continue
        code, suggestion = ISSUE_METADATA.get(
            check.name,
            (
                check.name.upper(),
                "Review this issue and update the input files or analysis configuration before proceeding.",
            ),
        )
        issues.append(
            ValidationIssue(
                severity=check.severity,
                code=code,
                message=check.message,
                suggestion=suggestion,
                details=check.details,
            )
        )
    return issues


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
