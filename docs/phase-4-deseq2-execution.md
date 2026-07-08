# Phase 4.7 Minimal DESeq2 Execution

Phase 4.7 adds the first gated real DESeq2 execution chain for Bulk RNA-seq.
It is intentionally minimal: DESeq2 can run only when explicitly requested and
only after the Phase 4.6 preflight reports that the environment is ready.

Phase 4.8 adds a deterministic interpretation summary for DESeq2 outputs. It
does not change the DESeq2 statistical execution, design formula, or runtime
gate.

## Purpose

This phase connects `POST /task/run` to a safe Rscript + DESeq2 execution path
for the planned `deseq2` formal method. The existing `minimal_cpm_log2fc`
workflow remains the default when no formal method is requested.

## Required Environment

DESeq2 execution requires:

- `R`
- `Rscript`
- `BiocManager`
- `DESeq2`

The service checks these through the Phase 4.6 preflight before running the
task-local R script. If preflight is not ready, no DESeq2 Rscript analysis is
started.

## Requesting DESeq2

DESeq2 is selected when either field is set to `deseq2`:

```json
{
  "task_id": "task_0001",
  "project_name": "demo_bulk_rnaseq",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "analysis_goal": ["qc", "differential_expression"],
  "group_column": "condition",
  "contrast": "treatment_vs_control",
  "metadata_file": "rnaseq_minimal/metadata.csv",
  "count_matrix_file": "rnaseq_minimal/counts.csv",
  "execution_mode": "formal_de_real",
  "analysis_method": "deseq2",
  "formal_de_method": "deseq2"
}
```

`execution_mode: "formal_de_real"` currently requires `analysis_method` or
`formal_de_method` to be `deseq2`.

## Input Validation

Phase 4.7 reuses the existing RNA-seq validation rules:

- `metadata.csv` requires `sample_id` and `condition`.
- Exactly two conditions are required.
- `counts.csv` requires `gene_id`.
- Sample IDs must align between metadata and count matrix.
- Counts must be numeric, finite, non-negative, and integer-like.
- Duplicate sample IDs, duplicate gene IDs, missing values, and zero-library
  samples are rejected.

The DESeq2 script also checks sample alignment before constructing the DESeq2
dataset.

## Execution

When preflight is ready, the service writes a deterministic task-local R script
and runs:

```powershell
Rscript --vanilla <task-output>\run_deseq2.R <metadata> <counts> <output>
```

The command is invoked with list arguments, `shell=False`, captured output, and
a timeout. Public errors are sanitized before returning to the API caller.

The R script uses:

```r
suppressPackageStartupMessages(library(DESeq2))
dds <- DESeqDataSetFromMatrix(countData = count_matrix, colData = metadata, design = ~ condition)
dds <- DESeq(dds)
res <- results(dds)
```

No package installation commands are called.

## Output Files

DESeq2 execution writes these files under
`BIOINFO_OUTPUT_ROOT/tasks/<task_id>/`:

- `deseq2_results.csv`
- `deseq2_interpretation_summary.json`
- `deseq2_summary.json`
- `deseq2_run_manifest.json`
- `report.md`

`deseq2_results.csv` contains real DESeq2 result columns:

- `gene_id`
- `baseMean`
- `log2FoldChange`
- `lfcSE`
- `stat`
- `pvalue`
- `padj`

`deseq2_interpretation_summary.json` records a safe interpretation contract:

- thresholds used: `padj <= 0.05` and `abs(log2FoldChange) >= 1.0`
- total genes tested
- genes with valid and NA adjusted p-values
- genes passing adjusted p-value threshold
- genes passing log2 fold-change threshold
- genes passing both default reporting thresholds
- top genes by adjusted p-value
- top genes by absolute log2 fold change
- warnings and limitations
- interpretation boundary

`deseq2_summary.json` records:

- `analysis_method: "deseq2"`
- `formal_de_method: "deseq2"`
- `formal_de_ready: true`
- `statistical_test_performed: true`
- `pvalue_available: true`
- `adjusted_pvalue_available: true`
- `external_tools_called: true`
- `external_tool: "Rscript"`
- `r_package: "DESeq2"`
- `design_formula: "~ condition"`
- input and result gene/sample counts
- `pvalue_column: "pvalue"`
- `adjusted_pvalue_column: "padj"`
- `interpretation_summary_file: "deseq2_interpretation_summary.json"`
- default interpretation thresholds
- genes passing the default reporting filter
- interpretation boundary
- limitations and warnings

`deseq2_run_manifest.json` records:

- `analysis_method: "deseq2"`
- `execution_mode: "formal_de_real"`
- `formal_de_method: "deseq2"`
- `command_invoked_safely: true`
- `shell_used: false`
- `package_installation_attempted: false`
- output files
- limitations

## Interpretation Boundaries

The report and interpretation summary explicitly state:

- Adjusted p-values control false discovery rate under the statistical model.
- Statistical significance is not the same as biological significance.
- log2FoldChange direction depends on DESeq2 contrast/reference level.
- Direction is reported as positive or negative log2FoldChange unless a
  contrast/reference is explicitly recorded.
- NA pvalue or padj can occur due to filtering, low counts, outlier handling,
  or model limitations.
- No batch correction or complex design was performed in this phase.
- No GO/KEGG/GSEA enrichment was performed.

Genes passing both default thresholds are reporting candidates only. They are
not automatically biologically meaningful, causal, clinical, or pathway-level
findings.

## Unavailable Environment

If DESeq2 is requested but the preflight is not ready, `POST /task/run`
returns a deterministic error:

```text
DESEQ2_PREFLIGHT_NOT_READY
```

The message is:

```text
DESeq2 execution is not available because the preflight check is not ready.
```

No DESeq2 analysis Rscript is run, no fake DESeq2 output is generated, and the
task is not marked as completed.

## What Is Not Implemented

- No edgeR execution.
- No limma execution.
- No GO/KEGG/GSEA enrichment.
- No pathway analysis.
- No visualization generation.
- No Snakemake or Nextflow workflow.
- No Docker runner for this path.
- No Coze calls.
- No database persistence.
- No package installation or package update.
- No `BiocManager::install`, `install.packages`, or GitHub package installation.

## Limitations

- The design formula is fixed to `~ condition`.
- Exactly two conditions are required.
- No batch correction is performed unless future metadata and model support are
  added.
- No complex design, interaction model, paired design, or covariate adjustment
  is implemented yet.
- Interpretation requires biological and experimental context.
