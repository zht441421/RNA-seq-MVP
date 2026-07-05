# Phase 1.7 Acceptance: Dockerized R/Bioconductor Runtime

This document records the real acceptance result for Phase 1.7 Dockerized
R/Bioconductor Runtime validation.

## Summary

Phase 1.7 was validated with the Dockerized R/Bioconductor runner in
`RUN_MODE=docker_r`.

- Docker image build: successful.
- Image name: `bioinformatics-agent-r-bulk-rnaseq:0.1`.
- R environment check: passed.
- Unit tests: `52 passed`.
- Docker smoke test: passed.
- Final run status: `completed`.
- Reliability grade: `B`.

Smoke command:

```bash
python scripts/smoke_docker_r.py --base-url http://127.0.0.1:8000
```

Artifact project:

```text
artifacts/proj_89ecfc4c5c2447fdabe32b9e6489a7b6
```

## R Environment

The Docker image contains the expected R/Bioconductor runtime:

| Component | Version |
| --- | --- |
| R | `4.4.1` |
| DESeq2 | `1.44.0` |
| edgeR | `4.2.2` |
| limma | `3.60.6` |
| ggplot2 | `3.5.1` |
| pheatmap | `1.0.12` |
| jsonlite | `1.8.8` |
| readr | `2.1.5` |

## Primary Analysis

- Primary method: `DESeq2`.
- `primary_method_status`: `completed_with_warning`.
- Main result artifact: `04_main_results/deseq2_results.csv`.
- Normalized count artifact: `07_tables/normalized_counts.csv`.
- Runtime status artifact: `09_environment/run_status.json`.
- R session artifact: `09_environment/r_session_info.txt`.

The small simulated dataset triggered a DESeq2 standard dispersion fit failure.
The runner used the documented gene-wise dispersion fallback:

```text
estimateSizeFactors -> estimateDispersionsGeneEst -> dispersions<- -> nbinomWaldTest
```

The fallback was recorded in `run_status.json` warnings:

```text
DESeq2 standard dispersion fit failed; used gene-wise dispersion fallback.
```

Fallback status does not allow reliability grade A.

## Validation

Validation artifacts were generated:

- `05_validation_results/edger_results.csv`: present.
- `05_validation_results/limma_voom_results.csv`: present.
- `05_validation_results/validation_comparison.csv`: present.
- `validation_consistency_score = 1`.

## Reliability Interpretation

The final reliability grade was `B`.

This grade was assigned because the primary DESeq2 analysis completed with
warning and the independent validation methods showed strong consistency.
Because the DESeq2 dispersion fallback was required, the result is capped below
grade A.

This acceptance result does not mean all real datasets will receive grade B or
grade A. Real reliability grades still depend on QC status, study design,
sample size, batch/group confounding, successful validation methods, and
validation consistency.

Strong conclusions remain gated by the reliability grade and documented
limitations.

