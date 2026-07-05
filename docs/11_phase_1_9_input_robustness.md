# Phase 1.9 Input Robustness + User Error Recovery

Phase 1.9 strengthens Bulk RNA-seq count matrix plus metadata input validation
and makes user-facing recovery guidance clearer.

This phase does not change:

- DESeq2, edgeR, or limma-voom statistical logic.
- Dockerfile or Docker runtime package installation.
- Supported omics type.
- Reliability core grading rules.

## Validation Issue Schema

QC and Coze prepare-analysis responses include structured validation issues:

```json
{
  "severity": "error",
  "code": "SAMPLE_ID_MISMATCH",
  "message": "Sample IDs do not align between metadata and count matrix.",
  "suggestion": "Ensure every sample column in the count matrix has exactly one matching row in metadata.",
  "details": {
    "missing_in_metadata": ["sample_x"],
    "missing_in_count_matrix": ["sample_y"]
  }
}
```

`severity=error` blocks `/run`. `severity=warning` is preserved in QC,
reports, and audit logs, but does not necessarily block analysis.

## Covered Input Problems

The QC layer now reports structured issues for:

- missing or unreadable count matrix files
- missing or unreadable metadata files
- missing `gene_id_column`
- missing `sample_id_column`
- missing `group_column`
- count matrix with no sample columns
- metadata with no sample rows or no usable sample IDs
- sample ID mismatch between count matrix and metadata
- duplicated metadata sample IDs
- missing group values
- fewer than two groups
- absent reference or test group
- group sample size warnings for fewer than two samples
- missing count values
- non-numeric count values
- negative count values
- non-integer-like count values
- duplicated gene IDs
- high fraction of all-zero genes
- extreme library size imbalance
- missing batch column
- possible batch/group confounding

## UI Behavior

The local `/ui` workflow displays validation issues after Inspect and Prepare
Analysis. Each issue shows:

- code
- severity
- message
- suggestion
- details

Errors are styled as prominent issue blocks. Warnings are shown with secondary
warning styling.

## Error Recovery

When an error is present:

1. Review the issue code and suggestion.
2. Fix the input file path, schema mapping, metadata rows, sample IDs, group
   labels, or count values.
3. Re-run Inspect and Prepare Analysis.
4. Proceed to run only after QC has no blocking errors.

Warnings should be reviewed and retained in the evidence package. They may
reduce reliability, depending on the warning and downstream validation status.

## Auditability

Structured validation issues are included in:

- `/projects/{project_id}/qc`
- `/coze/projects/{project_id}/prepare-analysis`
- local `/ui` validation issue panels
- `02_qc_report.md`
- `10_audit_log.json`

This makes user mistakes and recovery guidance traceable without relying on raw
Python exceptions.

