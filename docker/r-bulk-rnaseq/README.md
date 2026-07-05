# R Bulk RNA-seq Docker Runtime

This image provides the Phase 1 Bulk RNA-seq R/Bioconductor runtime used by
`RUN_MODE=docker_r`.

Image name:

```bash
bioinformatics-agent-r-bulk-rnaseq:0.1
```

## Included Runtime

- R and Rscript
- Bioconductor
- DESeq2
- edgeR
- limma
- ggplot2
- pheatmap
- jsonlite
- readr
- optparse

Packages are installed at image build time. The backend must not install R
packages during each analysis run.

## Build

Run from the repository root:

```bash
docker build -f docker/r-bulk-rnaseq/Dockerfile -t bioinformatics-agent-r-bulk-rnaseq:0.1 .
```

The Dockerfile keeps the base image pinned to
`bioconductor/bioconductor_docker:RELEASE_3_19`, disables online version
diagnosis, and installs all R packages through base R `install.packages()` with
manual Bioconductor `3.19` repositories. It also sets:

```dockerfile
ENV BIOCONDUCTOR_ONLINE_VERSION_DIAGNOSIS=FALSE
```

If build logs show:

```text
Bioconductor version map cannot be validated; is it misconfigured?
Bioconductor online version validation disabled
```

rebuild with the current Dockerfile. It completely bypasses BiocManager during
package installation and sets these repositories manually:

```text
https://bioconductor.org/packages/3.19/bioc
https://bioconductor.org/packages/3.19/data/annotation
https://bioconductor.org/packages/3.19/data/experiment
https://bioconductor.org/packages/3.19/workflows
https://packagemanager.posit.co/cran/2024-06-01
```

This avoids both `BiocManager::repositories()` and `BiocManager::install()` so
Docker builds do not depend on Bioconductor version map validation.

## Test The Runtime

Check package availability:

```bash
docker run --rm bioinformatics-agent-r-bulk-rnaseq:0.1
```

Run the bundled R script against the small example dataset:

```bash
docker run --rm \
  -v "$PWD:/workspace" \
  -w /workspace \
  bioinformatics-agent-r-bulk-rnaseq:0.1 \
  Rscript /opt/bioinformatics-agent/scripts/bulk_rnaseq_de.R \
  /workspace/artifacts/manual-test/09_environment/analysis_config.json
```

The backend generates `analysis_config.json` automatically when
`RUN_MODE=docker_r`.

## Backend Configuration

```bash
set RUN_MODE=docker_r
set DOCKER_R_IMAGE=bioinformatics-agent-r-bulk-rnaseq:0.1
set DOCKER_EXECUTABLE=docker
set DOCKER_WORKDIR=/workspace
uvicorn backend.app.main:app --reload
```
