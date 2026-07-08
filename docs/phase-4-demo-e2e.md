# Phase 4.4 Demo End-to-End Validation

Phase 4.4 adds stable project-local demo input data and a repeatable validation
script for the minimal Bulk RNA-seq MVP workflow.

## Demo Input Data

Demo inputs live under:

```text
data/demo/rnaseq_minimal/
```

Files:

- `metadata.csv`
- `counts.csv`
- `README.md`

The metadata file contains two conditions, `control` and `treatment`, with
three samples per condition. The count matrix uses `gene_id` as the first column
and sample columns that match `metadata.csv`.

The data is synthetic and intended only for MVP validation. It is not a
biological claim.

## Run the Demo

From the repository root:

```powershell
python scripts\run_phase_4_4_demo.py
```

The script uses FastAPI `TestClient`, so it does not require a live server. It
creates a task, prepares the registry through the existing plan and QC
endpoints, runs `POST /task/run` with `execution_mode: minimal_real`, then reads
the generated artifacts and public artifact/audit endpoints.

By default, the script uses:

- `BIOINFO_INPUT_ROOT`: `data/demo`
- `BIOINFO_OUTPUT_ROOT`: `data/outputs/phase_4_4_demo`

If those environment variables are already set, the script uses the configured
locations.

## Expected Artifacts

The demo validates that these files are generated under the task output
directory:

- `run_manifest.json`
- `execution_summary.json`
- `qc_summary.json`
- `normalized_counts_cpm.csv`
- `differential_expression_results.csv`
- `report.md`

## What Is Validated

The script checks that:

- A task can be created.
- The minimal run completes successfully.
- The task output directory exists.
- All expected artifacts exist.
- `execution_summary.json` records real MVP execution.
- `external_tools_called` is `false`.
- `statistical_test_performed` is `false`.
- The preliminary ranking table does not contain p-value, adjusted p-value,
  q-value, or significance fields.
- `report.md` contains conservative interpretation boundaries.
- Public run, artifact, and audit responses do not expose local absolute paths,
  tracebacks, tokens, passwords, secrets, or internal stack details.

On success, the script prints a concise deterministic summary and exits with
status code `0`. On validation failure, it exits with a non-zero status code.

## What Is Not Implemented Yet

Phase 4.4 does not add new RNA-seq algorithms. It does not run DESeq2, edgeR,
limma, Rscript, Snakemake, Nextflow, Docker, Coze, or external tools.

It does not produce p-values, adjusted p-values, q-values, enrichment results,
pathway results, statistical significance labels, or publication-level
biological conclusions.

## Difference From DESeq2, edgeR, Or limma

The current MVP computes QC metrics, CPM-normalized counts, a low-count filter,
and a deterministic exploratory log2 fold-change ranking from group mean CPM
values. DESeq2, edgeR, and limma fit formal statistical models and can estimate
uncertainty and adjusted statistical evidence. Those formal methods are outside
the Phase 4.4 scope and are reserved for future phases.
