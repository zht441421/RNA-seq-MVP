# Phase 4 Minimal Bulk RNA-seq MVP

Phase 4.1 introduces the first real internal Bulk RNA-seq execution path for
the task API. It reads real metadata and count matrix files, validates sample
alignment, computes basic QC metrics, writes CPM-normalized counts, and writes a
preliminary group-level log2 fold-change ranking when exactly two condition
groups are present.

Phase 4.2 strengthens the input content validation layer so invalid metadata or
count matrices fail deterministically before any analysis artifacts are
generated.

This phase is intentionally modest. It does not implement a formal
differential expression statistical method and does not report p-values or
adjusted p-values.

## Execution Trigger

`POST /task/run` keeps the dry-run behavior as the default when no input files
are supplied.

Minimal real execution is selected when both fields are supplied:

```json
{
  "task_id": "task_0001",
  "project_name": "demo_bulk_rnaseq",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "analysis_goal": ["qc", "differential_expression"],
  "group_column": "condition",
  "contrast": "treatment_vs_control",
  "metadata_file": "demo/metadata.csv",
  "count_matrix_file": "demo/counts.csv",
  "execution_mode": "minimal_real"
}
```

`execution_mode` is optional when both input files are present. The public
registry status remains `run_placeholder_ready` for compatibility with the
Phase 3 lifecycle contract, while generated files and execution summaries mark
the run as `minimal_analysis_completed`.

## Input Root

Input paths are resolved under `BIOINFO_INPUT_ROOT`. If it is not set, the
default input root is `data/inputs` under the repository.

Only safe relative paths are accepted. Absolute paths and path traversal are
rejected by the Phase 3.4 input validation layer.

## Phase 4.2 Content Validation

Minimal real execution validates file contents after path validation and before
creating analysis outputs. A validation failure returns `422 Unprocessable
Entity` with a stable public error shape:

```json
{
  "detail": {
    "error_code": "RNASEQ_INPUT_VALIDATION_FAILED",
    "message": "RNA-seq input validation failed.",
    "errors": [],
    "warnings": []
  }
}
```

The error details are deterministic and must not expose local absolute paths,
tracebacks, tokens, passwords, secrets, or internal stack details.

On validation failure, the task is not marked as a completed minimal analysis.
The registry may record `minimal_analysis_validation_failed`, and no analysis
output files are written.

## `metadata.csv`

Required columns:

- `sample_id`
- `condition`

Example:

```csv
sample_id,condition
sample_1,control
sample_2,control
sample_3,treatment
sample_4,treatment
```

Metadata content requirements:

- `sample_id` and `condition` are required.
- Empty files are rejected.
- Empty or whitespace-only `sample_id` and `condition` values are rejected.
- Duplicate `sample_id` values are rejected.
- At least two distinct samples are required.
- Exactly two condition groups are supported for Phase 4.2.
- One condition group is rejected as non-comparable.
- More than two condition groups are rejected as unsupported by the preliminary
  log2 fold-change workflow.

## `counts.csv`

The first column must be `gene_id`. All remaining columns must be sample IDs
that match `metadata.sample_id`.

Example:

```csv
gene_id,sample_1,sample_2,sample_3,sample_4
GeneA,100,120,250,260
GeneB,5,3,4,6
```

CSV, TSV, and tabular TXT files are supported through the existing safe suffix
contract.

Count matrix content requirements:

- The first column must be `gene_id`.
- Empty files are rejected.
- Empty or whitespace-only `gene_id` values are rejected.
- Duplicate `gene_id` values are rejected.
- Duplicate sample columns are rejected when detectable.
- Count values must be present, numeric, finite, non-negative, and integer-like.
- Missing, non-numeric, negative, and non-finite count values are rejected.
- Count sample columns must exactly match the metadata `sample_id` set.
- Extra or missing count sample columns are rejected.
- All-zero genes may be filtered by the low-count filter.
- Any all-zero sample, also called a zero-library sample, is rejected.

Sample alignment supports count columns in a different order from the metadata
rows. When the sample sets match, the executor reorders counts to metadata
sample order before writing outputs.

## Output Artifacts

Minimal real execution writes these files under
`BIOINFO_OUTPUT_ROOT/tasks/<task_id>/`:

- `run_manifest.json`
- `execution_summary.json`
- `qc_summary.json`
- `normalized_counts_cpm.csv`
- `differential_expression_results.csv`
- `report.md`

Public API responses expose only safe relative paths such as
`tasks/<task_id>/qc_summary.json`.

## What Is Real

- Metadata and count matrix files are read from disk.
- Required columns and sample alignment are validated.
- Metadata and count matrix content validation fails before output generation.
- Library sizes are computed from the count matrix.
- CPM-normalized counts are computed.
- Low-expression filtering is applied for the preliminary ranking with
  `min_total_count = 10`.
- `qc_summary.json`, `normalized_counts_cpm.csv`,
  `differential_expression_results.csv`, and `report.md` are generated from the
  submitted files.

## What Is Not Yet Implemented

- No DESeq2, edgeR, or limma execution.
- No Rscript or external command-line tool calls.
- No Snakemake, Nextflow, Docker, or Coze calls.
- No database persistence.
- No formal differential expression statistical test.
- No p-values, adjusted p-values, q-values, or false discovery rate estimates.
- No PCA coordinates.
- No GSEA, GO, KEGG, pathway, or enrichment analysis.

## Preliminary Ranking

`differential_expression_results.csv` is a preliminary ranking table, not a
formal differential expression result. It includes:

- `gene_id`
- `mean_cpm_group_1`
- `mean_cpm_group_2`
- `log2_fold_change`
- `total_count`
- `analysis_note`

It deliberately does not include `pvalue`, `padj`, `qvalue`, significance
labels, enrichment terms, or pathway results.

The log2 fold-change is computed from group mean CPM values with a +1 CPM
pseudocount for deterministic finite output. Group 1 and group 2 follow the
first-seen condition order in `metadata.csv`, and the `analysis_note` records
the mapping for each row.

## Limitations

This phase is useful for validating the task execution boundary and producing
small deterministic artifacts from real input files. It is not suitable for
biological decision-making, publication-grade differential expression, or
pathway interpretation.
