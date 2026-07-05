# Backend API

Base URL for local development:

```text
http://127.0.0.1:8000
```

## Coze Adapter APIs

High-level Coze-facing APIs are available under `/coze`. They wrap the lower
level project, file, QC, plan, run, result, and artifact APIs.

### POST /coze/projects

Create a project for a Coze workflow.

Request:

```json
{
  "project_name": "demo",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "organism": "human",
  "gene_id_type": "symbol",
  "annotation_version": "unknown"
}
```

Response includes `project_id`, `human_readable_summary`, and `next_action`.

### POST /coze/projects/{project_id}/inspect

Register local file paths and inspect schema candidates.

Request:

```json
{
  "count_matrix_path": "examples/real_small_count_matrix.csv",
  "metadata_path": "examples/real_small_metadata.csv"
}
```

Response includes detected gene ID candidates, sample columns, metadata columns,
possible sample ID column, possible group column, possible batch column,
warnings, and next action.

### POST /coze/projects/{project_id}/prepare-analysis

Run QC and create a recommended analysis plan after the user confirms schema
mapping.

If critical stop conditions exist, response uses `next_action: fix_input` and
does not create a runnable plan.

### POST /coze/projects/{project_id}/confirm-and-run

Confirm the plan and run analysis.

Request:

```json
{
  "confirmed": true,
  "run_mode": "mock",
  "analysis_plan_overrides": {}
}
```

If `confirmed=false`, no analysis is run. If `run_mode` is omitted, the backend
default `RUN_MODE` is used. The response includes run status, reliability grade,
allowed conclusion level, human-readable summary, and artifact manifest.

### GET /coze/projects/{project_id}/status

Return polling-friendly project stage and next action.

### GET /coze/projects/{project_id}/report

Return evidence-package markdown and audit content for Coze display. For grades
C, D, and E, `strong_conclusion_allowed` is always false.

See `docs/06_coze_adapter.md` for the recommended Coze workflow.

## POST /projects

Create a project.

Request:

```json
{
  "name": "bulk rnaseq demo",
  "description": "optional description"
}
```

Response includes `project_id` and status.

## POST /projects/{project_id}/files

Register Phase 1 input files.

MVP request:

```json
{
  "count_matrix_file": "examples/sample_count_matrix.csv",
  "metadata_file": "examples/sample_metadata.csv"
}
```

Future versions should support Coze upload URLs or multipart upload backed by
object storage.

## GET /system/r-env

Check whether the backend host can run the real R/Bioconductor runner.

The endpoint calls:

```text
Rscript backend/app/scripts/r/check_bioconductor_env.R
```

Response shape:

```json
{
  "r_available": true,
  "r_version": "4.x.x",
  "packages": {
    "DESeq2": { "installed": true, "version": "..." },
    "edgeR": { "installed": true, "version": "..." },
    "limma": { "installed": true, "version": "..." }
  },
  "ready_for_real_r": true,
  "missing_required": [],
  "missing_optional": []
}
```

If `Rscript` is unavailable, the endpoint returns `r_available: false`,
`ready_for_real_r: false`, and a structured error message. It does not install R
or any R packages.

Minimum required packages for `RUN_MODE=real_r` are `DESeq2`, `jsonlite`, and
`readr`. Recommended packages are `edgeR`, `limma`, `ggplot2`, and `pheatmap`.

## GET /system/docker-r-env

Check whether Docker can run the R/Bioconductor image configured by
`DOCKER_R_IMAGE`.

Response shape:

```json
{
  "docker_available": true,
  "image_available": true,
  "image_name": "bioinformatics-agent-r-bulk-rnaseq:0.1",
  "r_available_in_container": true,
  "packages": {
    "DESeq2": { "installed": true, "version": "..." },
    "edgeR": { "installed": true, "version": "..." },
    "limma": { "installed": true, "version": "..." }
  },
  "ready_for_docker_r": true,
  "missing_required": [],
  "errors": []
}
```

If Docker is unavailable or the image is missing, the endpoint returns
`ready_for_docker_r: false` with structured `errors`. It does not build images
or install packages automatically.

## POST /projects/{project_id}/inspect

Inspect registered files and return:

- File hashes.
- Columns.
- Row counts.
- Preview rows.
- Candidate schema fields.

## POST /projects/{project_id}/qc

Run QC using the confirmed schema and contrast configuration.

Request body follows `docs/02_input_schema.md`.

Response includes checks, group counts, sample alignment, library size summary,
low-count gene summary, and pass or fail status.

## POST /projects/{project_id}/plan

Generate a recommended analysis plan.

Response includes:

- Primary method: `DESeq2`.
- Validation methods: `edgeR`, `limma_voom`.
- Normalization: `DESeq2_size_factor`.
- Low-count filtering rule.
- FDR and log2FC thresholds.
- `requires_user_confirmation: true`.

## POST /projects/{project_id}/confirm-plan

Confirm or reject the proposed plan.

Request:

```json
{
  "plan_id": "plan-id",
  "confirmed": true
}
```

## POST /projects/{project_id}/run

Run the confirmed plan.

Behavior depends on `RUN_MODE`:

- `RUN_MODE=mock`: calls the mock runner and produces mock artifacts only.
- `RUN_MODE=real_r`: writes `analysis_config.json`, calls
  `Rscript backend/app/scripts/r/bulk_rnaseq_de.R analysis_config.json`, parses
  `run_status.json`, registers real-run artifacts, and grades reliability.
- `RUN_MODE=docker_r`: writes container-path `analysis_config.json`, mounts the
  project root into Docker at `DOCKER_WORKDIR`, runs the R script inside
  `DOCKER_R_IMAGE`, parses `run_status.json`, and grades reliability.

Real R mode outputs to:

```text
artifacts/{project_id}/
  04_main_results/deseq2_results.csv
  05_validation_results/edger_results.csv
  05_validation_results/limma_voom_results.csv
  05_validation_results/validation_comparison.csv
  06_figures/pca_plot.png
  06_figures/sample_distance_heatmap.png
  06_figures/volcano_deseq2.png
  06_figures/ma_plot_deseq2.png
  07_tables/normalized_counts.csv
  07_tables/significant_genes_deseq2.csv
  09_environment/r_session_info.txt
  09_environment/run_status.json
```

If DESeq2 fails, the endpoint still returns structured run status when possible,
with reliability grade `E`.

For local end-to-end validation, start the API with `RUN_MODE=real_r` and run:

```bash
python scripts/smoke_real_r.py --base-url http://127.0.0.1:8000
```

The smoke script uses `examples/real_small_count_matrix.csv` and
`examples/real_small_metadata.csv`.

For Dockerized R validation, build the image and run:

```bash
python scripts/smoke_docker_r.py --base-url http://127.0.0.1:8000
```

The API must be started with `RUN_MODE=docker_r`.

## GET /projects/{project_id}/status

Return project status and latest known workflow state.

## GET /projects/{project_id}/results

Return result metadata, reliability grade, run status, and report pointers. In
mock mode, `result_available` is false. In real R mode, `result_available` is
true only when the primary R run completed.

## GET /projects/{project_id}/artifacts

Return the evidence package `manifest.json` when it exists.

Manifest response shape:

```json
{
  "project_id": "proj_x",
  "generated_at": "2026-01-01T00:00:00+00:00",
  "artifact_root": "artifacts/proj_x",
  "run_mode": "mock",
  "files": [
    {
      "relative_path": "01_summary.md",
      "type": "report",
      "status": "present",
      "description": "Human-readable summary"
    }
  ]
}
```

If the evidence package has not been generated, the endpoint returns:

```json
{
  "project_id": "proj_x",
  "evidence_package_generated": false,
  "message": "Evidence package not generated; returning current artifact list.",
  "artifacts": []
}
```

## Evidence Package Structure

Each mock or real R run writes:

```text
artifacts/{project_id}/
  01_summary.md
  02_qc_report.md
  03_method_selection.md
  04_main_results/
  05_validation_results/
  06_figures/
  07_tables/
  08_reproducible_code/
  09_environment/
  10_audit_log.json
  11_reliability_report.md
  manifest.json
```

`manifest.json` lists standard files, standard directories, expected analysis
outputs, and any additional artifacts. Status values are `present`, `missing`,
or `not_applicable`.

`10_audit_log.json` contains:

- Project ID and creation time.
- Omics type and input level.
- Run mode.
- Input file paths, hashes, rows, and columns.
- Schema mapping.
- Primary method, validation methods, normalization, FDR, and log2FC threshold.
- QC status, warnings, and stop conditions.
- Run status and validation method status.
- Reliability grade and allowed conclusion level.
- Artifact list and environment references.

`11_reliability_report.md` explains the final reliability grade, satisfied and
failed conditions, stop conditions, downgrade conditions, whether strong
conclusions are allowed, and required improvements.
