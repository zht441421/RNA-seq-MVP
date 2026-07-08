# Phase 4.9 DESeq2 Demo End-to-End Validation

Phase 4.9 adds a dedicated small synthetic dataset and a deterministic
end-to-end validation script for the gated DESeq2 execution path.

## Purpose

The goal is to validate the existing DESeq2 pipeline contract with stable demo
inputs when the local DESeq2 preflight is ready. The demo does not add new
statistical methods, biological interpretation features, or public API schema
changes.

## Demo Data Location

Demo inputs live under:

```text
data/demo/deseq2_minimal/
```

Files:

- `metadata.csv`
- `counts.csv`
- `README.md`

The metadata has six synthetic samples: three `control` and three `treated`.
The count matrix has `gene_id` as the first column and sample columns that
exactly match `metadata.csv`.

## Synthetic Data Disclaimer

These files are synthetic demo data, not real biological data. Results from this
dataset are for pipeline validation only and are not for biological
interpretation.

## Run The Script

From the repository root:

```powershell
python scripts\run_phase_4_9_deseq2_demo.py
```

To require local DESeq2 availability in CI or a release check:

```powershell
python scripts\run_phase_4_9_deseq2_demo.py --require-deseq2
```

The script uses FastAPI `TestClient`, creates a task, calls
`GET /task/formal-de/preflight`, prepares the existing plan and QC lifecycle,
and then runs `POST /task/run` with:

- `execution_mode: formal_de_real`
- `analysis_method: deseq2`
- `formal_de_method: deseq2`
- `metadata_file: deseq2_minimal/metadata.csv`
- `count_matrix_file: deseq2_minimal/counts.csv`

By default, the script sets:

- `BIOINFO_INPUT_ROOT`: `data/demo`
- `BIOINFO_OUTPUT_ROOT`: `data/outputs/phase_4_9_deseq2_demo`

## When DESeq2 Is Unavailable

If preflight is not ready, the script prints a safe skipped message and exits
with code `0` by default. It does not create fake DESeq2 outputs.

With `--require-deseq2`, the same unavailable preflight exits with a
deterministic non-zero code.

## When DESeq2 Is Ready

If preflight is ready, the script runs the existing DESeq2 Rscript execution
chain and validates:

- the task run completed as `deseq2_analysis_completed`
- all expected files exist
- the artifacts endpoint lists the expected files
- the report includes DESeq2 interpretation boundaries
- the manifest records that package installation was not attempted

## Expected Artifacts

The script validates these files under the task output directory:

- `deseq2_results.csv`
- `deseq2_summary.json`
- `deseq2_run_manifest.json`
- `deseq2_interpretation_summary.json`
- `report.md`

## Interpretation Boundaries

The generated report remains bounded by the Phase 4.8 interpretation contract:

- Statistical significance is not the same as biological significance.
- Adjusted p-values depend on the DESeq2 statistical model.
- log2FoldChange direction depends on DESeq2 contrast/reference level.
- No GO/KEGG/GSEA enrichment analysis is performed.
- Synthetic demo results are pipeline validation outputs only.

## Not Implemented Items

Phase 4.9 does not implement:

- edgeR
- limma
- GSEA
- GO enrichment
- KEGG enrichment
- pathway analysis
- batch correction
- complex design formulas
- visualization generation
- Snakemake
- Nextflow
- Docker
- database persistence
- Coze API calls
- automatic R package installation
