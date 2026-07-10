# RNA-seq MVP / Bioinformatics Agent

This repository is the Phase 1 MVP of a bioinformatics-oriented multi-agent analysis platform.

The long-term goal is to build a Coze-based bioinformatics analysis agent that can guide researchers through omics data analysis, execute reproducible workflows, perform quality control, validate results, and generate auditable reports.

## Phase 1 Scope

Current Phase 1 focuses on validating the basic Bulk RNA-seq MVP structure.

The current version verifies:

- Project repository structure
- Bulk RNA-seq MVP workflow skeleton
- Input data checking logic
- Metadata and count matrix validation concept
- Evidence package design
- Audit log design
- Reliability-first analysis principle

## Core Principle

This project prioritizes reliability over speed.

The system should not directly generate strong biological conclusions unless the data quality, method selection, validation results, and reproducibility checks are sufficient.

## Current Status

## Current Phase 4 MVP Status

Phase 4 currently supports the default `minimal_cpm_log2fc` Bulk RNA-seq
workflow and an explicit `deseq2` workflow when `GET /task/formal-de/preflight`
reports readiness. Demo validation scripts are available at
`scripts/run_phase_4_4_demo.py` and `scripts/run_phase_4_9_deseq2_demo.py`.

Current limitations remain: no edgeR, limma, enrichment, batch correction,
complex design formulas, visualization generation, database persistence, or
real Coze API integration. Minimal results are exploratory, and synthetic demo
results are for pipeline validation only.

Phase 5 begins with a local SQLite persistent task storage foundation for task
metadata, status, lifecycle events, and artifact metadata.

Phase 5.2 adds `GET /task/{task_id}/artifacts/{artifact_name}/download` for
safe, task-scoped artifact downloads; see
`docs/phase-5-artifact-download-contract.md`.

Phase 5.3 adds `GET /task/{task_id}/coze-summary` for safe structured
task-result summaries intended for Coze and front-end consumption.

Phase 5.4 adds `POST /task/{task_id}/inputs/register` for safe task-scoped
metadata/count-matrix input registration under `BIOINFO_INPUT_ROOT`.

Phase 5.5 adds optional DESeq2/minimal contrast direction fields on
`POST /task/run`: `contrast_column`, `contrast_numerator`, and
`contrast_denominator`. When omitted, two-group metadata keeps the existing
deterministic inferred direction. When supplied, minimal CPM/log2FC and DESeq2
artifacts state that positive log2FC means higher expression in the numerator
relative to the denominator. See
`docs/phase-5-deseq2-contrast-control.md`.

Phase 5.6 adds a reproducible Coze-ready backend demo:
`python scripts\run_phase_5_6_coze_ready_demo.py`. The demo creates a task,
registers inputs, runs `minimal_cpm_log2fc` with explicit contrast, downloads
artifacts, fetches `coze-summary`, and verifies public responses are safe for
front-end or Coze presentation. See `docs/phase-5-6-coze-ready-demo.md`.

Phase 1 has been validated and tagged as:

```text
phase-1-bulk-rnaseq-mvp

# Bioinformatics Agent

Backend skeleton for a Coze-based multi-omics bioinformatics agent platform.

This repository currently implements Phase 1 through Phase 1.2: Bulk RNA-seq
count matrix plus sample metadata differential expression workflow
orchestration, optional real R execution, and R/Bioconductor environment
validation.
The focus is project structure, API contracts, input validation, QC rules,
analysis planning, reliability grading, auditability, and testability.

## Phase 1 MVP

Supported now:

- Bulk RNA-seq count matrix input.
- Sample metadata input.
- Field inspection and schema recommendation.
- Metadata and count matrix alignment checks.
- MVP QC rules for counts, groups, batches, library sizes, and low-count genes.
- Recommended analysis plan with DESeq2 as the primary method placeholder.
- edgeR and limma-voom validation placeholders.
- Mock pipeline runner and artifact manifest.
- Optional real R runner for count matrix differential expression.
- R/Bioconductor environment check endpoint.
- Dockerized R/Bioconductor runtime for machines without local Rscript.
- Phase 1.7 Dockerized R/Bioconductor Runtime: validated with docker_r smoke test.
- Phase 1.8 Real Analysis Report/UI Hardening: validated with pytest and docker_r smoke test.
- Phase 1.9 Input Robustness + User Error Recovery: validated with pytest and docker_r smoke test.
- Phase 1.10 Reproducibility Package + Run Replay: validated with pytest, docker_r smoke test, and replay dry-run.
- Phase 1.11 Result Table Interpretation Guardrails: validated with pytest, docker_r smoke test, and guarded report/UI output.
- Phase 1.12 Project Export Package: validated with pytest and docker_r smoke test.
- Phase 1.13 End-to-End Acceptance Suite: validated with pytest and acceptance report.
- Small simulated real-run dataset for local smoke testing.
- Standard evidence package with audit log, manifest, QC report, method report,
  and reliability report.
- Coze-facing high-level API adapter under `/coze`.
- Reliability grading rules that gate any strong conclusion.

Not implemented yet:

- FASTQ processing, alignment, quantification, or transcript-level import.
- Enrichment analysis.
- Persistent production database.
- Production task queue.
- Object storage such as MinIO or S3.
- Multi-tenant authentication and authorization.

## Quickstart

Phase 1 only supports Bulk RNA-seq count matrix + metadata.

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Build the Docker R/Bioconductor image:

```bash
docker build -f docker/r-bulk-rnaseq/Dockerfile -t bioinformatics-agent-r-bulk-rnaseq:0.1 .
```

3. Start FastAPI:

```bash
set RUN_MODE=docker_r
uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

4. Open the local UI:

```text
http://127.0.0.1:8001/ui
```

5. Run docker smoke:

```bash
python scripts/smoke_docker_r.py --base-url http://127.0.0.1:8001
```

6. Run final acceptance:

```bash
python scripts/acceptance_phase_1.py --base-url http://127.0.0.1:8001
```

## Run Locally

Create a virtual environment and install development dependencies:

```bash
cd bioinformatics-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run tests:

```bash
pytest
```

Start the FastAPI backend:

```bash
uvicorn backend.app.main:app --reload
```

Open the API docs at:

```text
http://127.0.0.1:8000/docs
```

Open the local Coze workflow simulator at:

```text
http://127.0.0.1:8000/ui
```

This page uses vanilla JavaScript to call the existing `/coze` APIs and run the
Bulk RNA-seq mock workflow locally.

## MVP Happy Path

The intended Phase 1 chain is:

```text
create project -> register files -> inspect -> QC -> plan -> confirm plan -> mock run -> artifacts
```

Example input files are available in `examples/`.

For the file registration endpoint, this MVP accepts local file paths. A future
version should replace this with Coze upload handling backed by object storage.

## Run Modes

The backend supports three run modes:

- `RUN_MODE=mock`: default. Produces mock outputs only.
- `RUN_MODE=real_r`: calls `Rscript backend/app/scripts/r/bulk_rnaseq_de.R`.
- `RUN_MODE=docker_r`: calls the same R script inside a Docker image.

Real R mode accepts only count matrix plus metadata inputs. It does not process
FASTQ, alignment, or quantification files.

Check whether the current backend can run real R analysis:

```text
GET http://127.0.0.1:8000/system/r-env
```

The endpoint calls `backend/app/scripts/r/check_bioconductor_env.R` through
`Rscript` and returns installed package versions plus missing required and
optional packages. If `Rscript` is missing, the endpoint returns a structured
`ready_for_real_r: false` response rather than failing with an unhandled error.

Check whether Docker can run the bundled R/Bioconductor image:

```text
GET http://127.0.0.1:8000/system/docker-r-env
```

This endpoint uses Docker to run the same environment checker inside
`DOCKER_R_IMAGE`.

Example:

```bash
set RUN_MODE=real_r
set RSCRIPT_EXECUTABLE=Rscript
uvicorn backend.app.main:app --reload
```

The R script checks for these packages and does not install them automatically:

- `DESeq2`
- `edgeR`
- `limma`
- `ggplot2`
- `pheatmap`
- `jsonlite`
- `readr`

Minimum real-run requirements are `DESeq2`, `jsonlite`, and `readr`. `edgeR`,
`limma`, `ggplot2`, and `pheatmap` are recommended for validation and figures.
If `DESeq2` is missing, the primary method fails and reliability is `E`. If
`edgeR` or `limma` is missing, validation is skipped or failed while preserving
the DESeq2 status.

Real-run artifacts are written under:

```text
artifacts/{project_id}/
```

Key outputs include DESeq2 results, optional edgeR and limma-voom validation
results, validation comparison, figures, normalized counts, R session info, and
`run_status.json`.

Run the real R smoke test after starting the API with `RUN_MODE=real_r`:

```bash
python scripts/smoke_real_r.py --base-url http://127.0.0.1:8000
```

If `/system/r-env` reports `ready_for_real_r: false`, the smoke script prints
the missing packages and exits without marking the test as failed. If the
environment is ready, it runs:

```text
create project -> files -> inspect -> QC -> plan -> confirm plan -> real_r run -> status/results/artifacts
```

The smoke test checks for `run_status.json`, `deseq2_results.csv`, and
`r_session_info.txt`. If edgeR or limma is installed, it also expects
`validation_comparison.csv`.

## Docker R Runtime

Build the R/Bioconductor image from the repository root:

```bash
docker build -f docker/r-bulk-rnaseq/Dockerfile -t bioinformatics-agent-r-bulk-rnaseq:0.1 .
```

Test the image directly:

```bash
docker run --rm bioinformatics-agent-r-bulk-rnaseq:0.1
```

Run the backend with Dockerized R:

```bash
set RUN_MODE=docker_r
set DOCKER_R_IMAGE=bioinformatics-agent-r-bulk-rnaseq:0.1
set DOCKER_EXECUTABLE=docker
set DOCKER_WORKDIR=/workspace
uvicorn backend.app.main:app --reload
```

Run the Docker smoke test:

```bash
python scripts/smoke_docker_r.py --base-url http://127.0.0.1:8000
```

If Docker or the image is unavailable, the smoke script prints the missing
condition and exits without treating the skip as a failure. If
`ready_for_docker_r=true`, it runs the full API chain and checks for
`run_status.json`, `deseq2_results.csv`, `r_session_info.txt`,
`10_audit_log.json`, `11_reliability_report.md`, and `manifest.json`.

Small simulated datasets can occasionally cause DESeq2 standard dispersion
curve fitting to fail. The R runner then tries the documented gene-wise
dispersion fallback, records
`DESeq2 standard dispersion fit failed; used gene-wise dispersion fallback.` in
`run_status.json`, and sets `primary_method_status=completed_with_warning` if
the fallback succeeds. That status can still produce DESeq2 artifacts, but it
cannot receive reliability grade A.

`real_r` uses a host-local `Rscript`; `docker_r` mounts the project root into
the Docker image and runs R in the container. Neither mode supports FASTQ,
Nextflow, Snakemake, Coze upload handling, or other omics types.

## Phase 1.7 Real Analysis Validation

Use this path to validate real DESeq2 / edgeR / limma-voom execution without
depending on a host-local R installation:

1. Install Docker Desktop and make sure Docker is running.
2. Build the R/Bioconductor image:

```powershell
scripts\build_r_docker_image.ps1
```

or:

```bash
scripts/build_r_docker_image.sh
```

3. Test the image without FastAPI:

```powershell
scripts\test_r_docker_image.ps1
```

or:

```bash
scripts/test_r_docker_image.sh
```

4. Start FastAPI with Dockerized R:

```powershell
$env:RUN_MODE = "docker_r"
$env:DOCKER_R_IMAGE = "bioinformatics-agent-r-bulk-rnaseq:0.1"
uvicorn backend.app.main:app --reload
```

5. Confirm the backend environment:

```text
http://127.0.0.1:8000/system/docker-r-env
```

6. Open the local workflow UI:

```text
http://127.0.0.1:8000/ui
```

7. Use the example files, select `docker_r` in Step 4, and run.
8. Confirm artifacts under `artifacts/{project_id}/`, including
   `04_main_results/deseq2_results.csv`, `09_environment/run_status.json`,
   `09_environment/r_session_info.txt`, `10_audit_log.json`,
   `11_reliability_report.md`, and `manifest.json`.
9. Review the final reliability grade. Grades C, D, and E remain exploratory or
   blocked and must not be treated as strong scientific conclusions.
   `completed_with_warning` from the DESeq2 dispersion fallback is also capped
   below grade A.

For detailed troubleshooting, see `docs/08_real_analysis_validation.md`.

## Evidence Package

Every completed or failed run that reaches the runner step generates a standard
evidence package under:

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
  12_interpretation_summary.md
  manifest.json
```

Empty standard directories are created intentionally. Missing files are recorded
in `manifest.json` as `missing` or `not_applicable`; real analysis result tables
are not overwritten by report generation.

`10_audit_log.json` records input file hashes, schema mapping, methods, QC
status, run status, reliability grade, generated artifacts, and environment
references. `11_reliability_report.md` explains why the final reliability grade
was assigned and what would be required to improve it.
`12_interpretation_summary.md` summarizes result tables as candidate statistical
signals with explicit guardrails. It does not turn differential expression rows
into strong biological conclusions.

`GET /projects/{project_id}/artifacts` returns `manifest.json` when the evidence
package exists. If not, it returns the current in-memory artifact list with an
`evidence_package_generated: false` message.

## Project Export Package

Create a zip archive of an existing evidence package:

```text
POST /projects/{project_id}/export
```

Read existing export metadata:

```text
GET /projects/{project_id}/export
```

The archive is written to:

```text
exports/{project_id}/{project_id}_evidence_package.zip
```

It contains the evidence package, reproducibility bundle,
`12_interpretation_summary.md`, `manifest.json`, and a zip-level
`EXPORT_MANIFEST.json` with file hashes and run summary metadata. Export is a
packaging step only: it does not rerun analysis, change reliability grade, or
permit stronger scientific conclusions.

## Coze Adapter

The `/coze` API provides a higher-level workflow surface for Coze plugins or
workflows:

```text
POST /coze/projects
POST /coze/projects/{project_id}/inspect
POST /coze/projects/{project_id}/prepare-analysis
POST /coze/projects/{project_id}/confirm-and-run
GET  /coze/projects/{project_id}/status
GET  /coze/projects/{project_id}/report
```

The adapter returns Coze-friendly fields such as `human_readable_summary`,
`next_action`, `warnings`, `stop_conditions`, `reliability_grade`,
`allowed_conclusion_level`, and `artifact_manifest`.

Current MVP behavior still uses local file path registration instead of real
Coze file upload.

Run the adapter smoke test:

```bash
python scripts/smoke_coze_adapter.py --base-url http://127.0.0.1:8000
```

The default smoke run uses `examples/real_small_count_matrix.csv`,
`examples/real_small_metadata.csv`, and `run_mode=mock`, so it can run without R
or Docker.

## Design Principles

- The backend must not present AI-generated scientific conclusions as final
  claims.
- Strong conclusions require reliability grade A or B.
- Result interpretation summaries must use guarded language such as candidate
  statistical signals, and must respect `completed_with_warning` and C/D/E
  reliability limits.
- Reliability grade must be visible in generated results and reports.
- Every workflow step should leave enough structured state for audit logs.
- Runners are replaceable interfaces. Mock mode remains the default; real R mode
  and Dockerized R mode are available for count matrix workflows.
- Storage and database code are placeholders that can be swapped later.
