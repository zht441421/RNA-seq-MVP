# Real Analysis Environment Validation

Phase 1.7 focuses on validating that real Bulk RNA-seq differential expression
can run in the Dockerized R/Bioconductor runtime and produce the expected
artifacts. This phase does not add new omics types, FASTQ support, object
storage, Coze web integration, Nextflow, or Snakemake.

## Prerequisites

Install Docker Desktop and make sure the Docker engine is running before using
`RUN_MODE=docker_r`.

Quick checks:

```bash
docker --version
docker info
```

On Windows, start Docker Desktop first. If `docker info` cannot connect to the
engine, restart Docker Desktop and wait until it reports that the engine is
running.

## Build The R/Bioconductor Image

The expected image name is:

```text
bioinformatics-agent-r-bulk-rnaseq:0.1
```

From the repository root, run one of the helper scripts:

```powershell
scripts\build_r_docker_image.ps1
```

or:

```bash
scripts/build_r_docker_image.sh
```

Equivalent manual command:

```bash
docker build -f docker/r-bulk-rnaseq/Dockerfile -t bioinformatics-agent-r-bulk-rnaseq:0.1 .
```

R packages are installed at image build time. The backend and runners must not
install Bioconductor packages during each analysis task.

The Dockerfile pins the base image to
`bioconductor/bioconductor_docker:RELEASE_3_19`, sets
`BIOCONDUCTOR_ONLINE_VERSION_DIAGNOSIS=FALSE`, and installs all R packages with
base R `install.packages()` using manual Bioconductor `3.19` repositories. It
does not call `BiocManager::repositories()` or `BiocManager::install()`.

## Test The Image Without FastAPI

Run the local image checker:

```powershell
scripts\test_r_docker_image.ps1
```

or:

```bash
scripts/test_r_docker_image.sh
```

The script checks Docker availability, verifies that the image exists, mounts
the project into `/workspace`, and runs:

```text
Rscript backend/app/scripts/r/check_bioconductor_env.R
```

The JSON output should include package versions and:

```json
{
  "ready_for_real_r": true,
  "missing_required": []
}
```

Required packages for real analysis are `DESeq2`, `jsonlite`, and `readr`.
Recommended validation and figure packages are `edgeR`, `limma`, `ggplot2`, and
`pheatmap`.

## Check FastAPI Docker R Environment

Start FastAPI, then call:

```text
GET http://127.0.0.1:8000/system/docker-r-env
```

Expected ready response:

```json
{
  "docker_available": true,
  "image_available": true,
  "image_name": "bioinformatics-agent-r-bulk-rnaseq:0.1",
  "r_available_in_container": true,
  "ready_for_docker_r": true,
  "missing_required": [],
  "errors": []
}
```

If `ready_for_docker_r` is false, do not start real analysis yet. Resolve the
reported missing condition first.

## Start FastAPI With docker_r

PowerShell:

```powershell
$env:RUN_MODE = "docker_r"
$env:DOCKER_R_IMAGE = "bioinformatics-agent-r-bulk-rnaseq:0.1"
$env:DOCKER_EXECUTABLE = "docker"
$env:DOCKER_WORKDIR = "/workspace"
uvicorn backend.app.main:app --reload
```

Bash:

```bash
export RUN_MODE=docker_r
export DOCKER_R_IMAGE=bioinformatics-agent-r-bulk-rnaseq:0.1
export DOCKER_EXECUTABLE=docker
export DOCKER_WORKDIR=/workspace
uvicorn backend.app.main:app --reload
```

After restarting, re-check:

```text
http://127.0.0.1:8000/system/docker-r-env
```

## Run The Docker Smoke Test

With FastAPI running in `RUN_MODE=docker_r`:

```bash
python scripts/smoke_docker_r.py --base-url http://127.0.0.1:8000
```

If Docker or the image is unavailable, the smoke script prints the missing
condition and exits as a skip. If the environment is ready, it runs:

```text
create project -> register files -> inspect -> QC -> plan -> confirm plan -> docker_r run -> status -> results -> artifacts
```

The smoke script checks the required real-run evidence package outputs.

The small simulated dataset may trigger DESeq2's dispersion curve fitting error:

```text
all gene-wise dispersion estimates are within 2 orders of magnitude from the minimum value
```

In that case, the R runner falls back to gene-wise dispersion estimates:

```r
dds <- estimateSizeFactors(dds)
dds <- estimateDispersionsGeneEst(dds)
dispersions(dds) <- mcols(dds)$dispGeneEst
dds <- nbinomWaldTest(dds)
```

If fallback succeeds, `run_status.json` records
`primary_method_status: completed_with_warning` and includes this warning:

```text
DESeq2 standard dispersion fit failed; used gene-wise dispersion fallback.
```

This can still produce `deseq2_results.csv`, normalized counts, session info,
and validation artifacts, but it cannot receive reliability grade A. If
validation succeeds and consistency is at least `0.6`, the best possible grade
is B; without completed validation, the best possible grade is C.

## Run Through The Local UI

Open:

```text
http://127.0.0.1:8000/ui
```

Use the default example files:

```text
examples/real_small_count_matrix.csv
examples/real_small_metadata.csv
```

Then:

1. Create Project.
2. Inspect Files.
3. Confirm Schema Mapping.
4. In Step 4, select `docker_r`.
5. Confirm and Run.
6. Get Report.

If the final report says strong conclusions are not allowed, keep the result as
exploratory. Do not override reliability gating.

## Expected Artifacts

After a successful real Docker run, inspect:

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
  10_audit_log.json
  11_reliability_report.md
  manifest.json
```

Some validation artifacts may be absent if optional validation packages are
missing. The reliability grade must reflect that limitation.

## Troubleshooting

### Docker is not available

Symptoms:

- `/system/docker-r-env` returns `docker_available: false`.
- The local test script cannot find `docker`.

Fix:

- Install Docker Desktop.
- Start Docker Desktop.
- Confirm `docker --version` and `docker info` work in the same shell that runs
  FastAPI.

### Image is missing

Symptoms:

- `/system/docker-r-env` returns `image_available: false`.
- `docker image inspect bioinformatics-agent-r-bulk-rnaseq:0.1` fails.

Fix:

```bash
docker build -f docker/r-bulk-rnaseq/Dockerfile -t bioinformatics-agent-r-bulk-rnaseq:0.1 .
```

or use the provided build script.

### R packages are missing

Symptoms:

- `ready_for_docker_r: false`.
- `missing_required` includes `DESeq2`, `jsonlite`, or `readr`.

Fix:

- Rebuild the Docker image.
- Review `docker/r-bulk-rnaseq/Dockerfile`.
- Do not install packages during an analysis run.

### Bioconductor version map validation fails during build

Symptoms:

```text
Bioconductor version map cannot be validated; is it misconfigured?
Bioconductor online version validation disabled
```

Fix:

- Keep the base image as `bioconductor/bioconductor_docker:RELEASE_3_19`.
- Keep `BIOCONDUCTOR_ONLINE_VERSION_DIAGNOSIS=FALSE`.
- Completely bypass BiocManager during Docker builds.
- Use base R `install.packages()` with manual Bioconductor `3.19`
  repositories:

```text
BioCsoft=https://bioconductor.org/packages/3.19/bioc
BioCann=https://bioconductor.org/packages/3.19/data/annotation
BioCexp=https://bioconductor.org/packages/3.19/data/experiment
BioCworkflows=https://bioconductor.org/packages/3.19/workflows
CRAN=https://packagemanager.posit.co/cran/2024-06-01
```

- Rebuild with:

```bash
docker build -f docker/r-bulk-rnaseq/Dockerfile -t bioinformatics-agent-r-bulk-rnaseq:0.1 .
```

The current Dockerfile follows this strategy so build-time package resolution
does not depend on Bioconductor version map validation.

### Path mount problems

Symptoms:

- Container starts but cannot find `backend/app/scripts/r/bulk_rnaseq_de.R`.
- Container cannot find example inputs or output artifacts.

Fix:

- Run scripts from the repository root, or use the provided helper scripts.
- Confirm the project root is mounted at `/workspace`.
- Confirm `DOCKER_WORKDIR=/workspace`.
- Avoid moving input files outside the mounted project root during local
  validation.

### Analysis completes but reliability is C, D, or E

This is expected when validation is missing, QC has serious warnings, DESeq2
fails, or required artifacts are missing. Do not relax reliability rules to
force a stronger conclusion.
