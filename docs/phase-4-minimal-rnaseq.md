# Phase 4 Minimal Bulk RNA-seq MVP

Phase 4.1 introduces the first real internal Bulk RNA-seq execution path for
the task API. It reads real metadata and count matrix files, validates sample
alignment, computes basic QC metrics, writes CPM-normalized counts, and writes a
preliminary group-level log2 fold-change ranking when exactly two condition
groups are present.

Phase 4.2 strengthens the input content validation layer so invalid metadata or
count matrices fail deterministically before any analysis artifacts are
generated.

Phase 4.3 improves the human-readable `report.md` artifact. The report now
summarizes the analyzed inputs, validation checks, QC metrics, CPM
normalization, preliminary log2 fold-change ranking, generated artifacts,
limitations, and recommended next steps. This is a reporting-only improvement;
it does not add formal differential expression statistics.

Phase 4.4 adds stable project-local demo inputs and an end-to-end validation
script for reproducible acceptance testing. This is a reproducibility and
validation improvement only; it does not add new RNA-seq algorithms.

Phase 4.5 adds an explicit analysis method contract for the current minimal
workflow and the future formal differential expression methods. It records
method metadata in the generated outputs and keeps the minimal method clearly
separate from formal methods.

Phase 4.6 adds a separate DESeq2 environment preflight endpoint for future
formal method support. It does not change the minimal execution method and does
not run DESeq2 analysis.

Phase 4.7 adds a separate gated DESeq2 execution path. It does not change the
default minimal execution method.

Phase 4.8 adds deterministic DESeq2 interpretation summaries for the separate
DESeq2 path. It does not change the default minimal execution method.

The minimal workflow remains intentionally modest. It does not implement a
formal differential expression statistical method and does not report p-values
or adjusted p-values.

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
  "execution_mode": "minimal_real",
  "analysis_method": "minimal_cpm_log2fc"
}
```

`execution_mode` is optional when both input files are present. The public
registry status remains `run_placeholder_ready` for compatibility with the
Phase 3 lifecycle contract, while generated files and execution summaries mark
the run as `minimal_analysis_completed`.

`analysis_method` is optional for minimal real execution. When omitted and both
input files are supplied, the current method defaults to
`minimal_cpm_log2fc`.

If `analysis_method` or `formal_de_method` is explicitly set to `deseq2`, the
request is routed to the Phase 4.7 formal DESeq2 path instead of the minimal
workflow. DESeq2 requires preflight readiness and writes separate DESeq2
artifacts.

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

- The default minimal workflow does not run DESeq2, edgeR, or limma.
- The default minimal workflow does not call Rscript or external command-line tools.
- edgeR and limma execution are not implemented.
- No Snakemake, Nextflow, Docker, or Coze calls.
- No database persistence.
- No formal differential expression statistical test is run by the default
  minimal method.
- No p-values, adjusted p-values, q-values, or false discovery rate estimates
  are produced by the default minimal method.
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
- `analysis_method`
- `formal_statistical_test`
- `pvalue_available`
- `adjusted_pvalue_available`

It deliberately does not include `pvalue`, `padj`, `qvalue`, significance
labels, enrichment terms, or pathway results.

The log2 fold-change is computed from group mean CPM values with a +1 CPM
pseudocount for deterministic finite output. Group 1 and group 2 follow the
first-seen condition order in `metadata.csv`, and the `analysis_note` records
the mapping for each row.

## Phase 4.3 Enhanced Report

`report.md` is structured for cautious human review of the minimal MVP outputs.
It includes:

- Analysis summary with `task_id`, execution mode, sample count, gene count,
  retained gene count, condition groups, and generated artifacts.
- Input validation summary for metadata validation, count matrix validation,
  required columns, and sample ID alignment.
- QC summary with library sizes per sample, condition counts, and the
  low-expression filter threshold.
- Normalization summary explaining that CPM is library-size normalization and
  does not replace formal differential expression modeling.
- Preliminary log2 fold-change section explaining that ranking is based on
  group-level mean CPM comparison for exactly two conditions.
- A small deterministic table of top preliminary ranked genes by absolute
  log2 fold change.
- Generated artifact list using safe relative paths.
- Limitations and recommended next steps.

The top ranked genes are exploratory only. They can help users inspect large
group-level CPM differences before a formal method is added, but they are not
publication-level differential expression results.

Phase 4.3 keeps the interpretation boundaries explicit:

- No DESeq2, edgeR, or limma analysis is run yet.
- No formal statistical test is performed yet.
- No p-values, adjusted p-values, or q-values are produced yet.
- No batch correction is performed yet.
- No enrichment analysis is performed yet.
- No pathway analysis is performed yet.

Before formal differential expression analysis, users should verify sample
metadata design, inspect QC metrics, confirm biological replicates, and consider
batch design. Future phases may add DESeq2, edgeR, or limma support after those
analysis boundaries are implemented.

## Phase 4.4 Demo Data And E2E Script

Phase 4.4 adds deterministic demo data under:

```text
data/demo/rnaseq_minimal/
```

The demo includes:

- `metadata.csv` with two conditions and three samples per condition.
- `counts.csv` with integer non-negative counts and matching sample columns.
- `README.md` documenting the synthetic MVP validation data.

The end-to-end script is:

```powershell
python scripts\run_phase_4_4_demo.py
```

The script uses FastAPI `TestClient` and does not require a live server. It
creates a task, runs the existing plan and QC endpoints to satisfy registry
transition guards, executes the minimal real RNA-seq path, verifies expected
artifacts, checks execution flags, reads the public artifact and audit
endpoints, and prints a concise deterministic validation summary.

The script validates:

- Minimal run completion.
- Presence of `run_manifest.json`, `execution_summary.json`, `qc_summary.json`,
  `normalized_counts_cpm.csv`, `differential_expression_results.csv`, and
  `report.md`.
- `real_execution_performed` is `true`.
- `external_tools_called` is `false`.
- `statistical_test_performed` is `false`.
- The preliminary ranking output does not contain p-values, adjusted p-values,
  q-values, or statistical significance fields.
- The report preserves interpretation boundaries.
- Public responses do not expose local absolute paths or sensitive internal
  details.

Phase 4.4 still does not implement DESeq2, edgeR, limma, formal differential
expression statistics, p-values, adjusted p-values, q-values, enrichment
analysis, pathway analysis, or fake biological conclusions.

## Phase 4.5 Formal DE Contract

Phase 4.5 keeps the current execution method as:

```text
minimal_cpm_log2fc
```

This method performs CPM normalization and preliminary group-level log2
fold-change ranking only. It does not fit a formal statistical model, so
p-values and adjusted p-values are still unavailable.

The formal differential expression method names tracked by the contract are:

- DESeq2
- edgeR
- limma

The minimal real workflow records the method contract in
`execution_summary.json`:

- `analysis_method: "minimal_cpm_log2fc"`
- `analysis_method_display_name: "Minimal CPM + preliminary log2 fold-change ranking"`
- `formal_de_method: null`
- `formal_de_ready: false`
- `statistical_test_performed: false`
- `pvalue_available: false`
- `adjusted_pvalue_available: false`
- `external_tools_called: false`
- `method_limitations`
- `next_supported_formal_methods: ["deseq2", "edger", "limma"]`

It also records compatible metadata in `run_manifest.json`:

- `analysis_method: "minimal_cpm_log2fc"`
- `execution_mode: "minimal_real"`
- `formal_de_ready: false`
- `requested_formal_method: null`
- `supported_future_formal_methods: ["deseq2", "edger", "limma"]`

`differential_expression_results.csv` remains a preliminary ranking table. It
adds only method metadata fields:

- `analysis_method`
- `formal_statistical_test`
- `pvalue_available`
- `adjusted_pvalue_available`

In Phase 4.7, `deseq2` is routed to the gated DESeq2 execution path when
preflight is ready. If preflight is not ready, the API returns:

```text
DESEQ2_PREFLIGHT_NOT_READY
```

If a request sets `analysis_method` or `formal_de_method` to `edger` or
`limma`, the API returns a deterministic not-implemented error:

```json
{
  "detail": {
    "error_code": "FORMAL_DE_METHOD_NOT_IMPLEMENTED",
    "message": "Formal differential expression method is planned but not implemented in this phase.",
    "requested_method": "edger",
    "supported_current_methods": ["minimal_cpm_log2fc", "deseq2"],
    "supported_future_formal_methods": ["deseq2", "edger", "limma"],
    "errors": [
      "Requested formal differential expression method 'edger' is not implemented yet.",
      "No DESeq2, edgeR, limma, Rscript, or external tool execution was started."
    ]
  }
}
```

No output analysis files are generated for an unsupported formal method
request, and the task is not marked as `minimal_analysis_completed`.

## Phase 4.6 DESeq2 Preflight

`GET /task/formal-de/preflight` checks whether the local environment appears
ready for future DESeq2 execution. It can check R and Rscript availability,
read their versions, and test whether `BiocManager` and `DESeq2` are installed.

This endpoint is read-only:

- It does not require a `task_id`.
- It does not mutate the task registry.
- It does not create task artifacts.
- It does not install or update R packages.
- It does not call `BiocManager::install`.
- It does not run real DESeq2 differential expression analysis.

When R, Rscript, BiocManager, or DESeq2 is unavailable, the endpoint returns
HTTP 200 with `ready: false` and a clear limitation:

```text
DESeq2 execution is not available until R, Rscript, BiocManager, and DESeq2 are installed.
```

The minimal `POST /task/run` workflow still uses `minimal_cpm_log2fc` only and
still does not call Rscript, DESeq2, edgeR, limma, enrichment tools, containers,
workflow engines, or Coze.

## Phase 4.7 Minimal DESeq2 Execution

Phase 4.7 adds a separate formal DESeq2 path for explicit requests:

```json
{
  "execution_mode": "formal_de_real",
  "analysis_method": "deseq2",
  "formal_de_method": "deseq2"
}
```

The request still requires validated `metadata_file` and `count_matrix_file`.
The DESeq2 path is gated by the Phase 4.6 preflight. If the preflight is ready,
the service runs a task-local R script through `Rscript --vanilla` with design
formula `~ condition` and writes:

- `deseq2_results.csv`
- `deseq2_interpretation_summary.json`
- `deseq2_summary.json`
- `deseq2_run_manifest.json`
- `report.md`

`deseq2_results.csv` may include formal DESeq2 result columns such as
`baseMean`, `log2FoldChange`, `lfcSE`, `stat`, `pvalue`, and `padj`. These
columns belong to the DESeq2 output only. The minimal
`differential_expression_results.csv` artifact remains a preliminary
CPM/log2FC ranking.

## Phase 4.8 DESeq2 Interpretation Summary

Phase 4.8 writes `deseq2_interpretation_summary.json` for successful DESeq2
runs. The summary records default reporting thresholds, counts of genes passing
adjusted p-value and log2 fold-change thresholds, top genes by adjusted
p-value, top genes by absolute log2 fold change, warnings, limitations, and a
clear interpretation boundary.

The default thresholds are:

- `padj <= 0.05`
- `abs(log2FoldChange) >= 1.0`

The interpretation summary does not invent biological conclusions. It does not
claim pathway enrichment, causal biology, clinical significance, or gene
annotations. It also does not change the minimal `minimal_cpm_log2fc` output,
which remains a preliminary ranking without formal p-values.

The DESeq2 path does not install R packages, call `BiocManager::install`, run
edgeR or limma, perform GO/KEGG/GSEA enrichment, use Docker, run workflow
engines, call Coze, or add database persistence.

## Limitations

This phase is useful for validating the task execution boundary and producing
small deterministic artifacts from real input files. It is not suitable for
biological decision-making, publication-grade differential expression, or
pathway interpretation.
