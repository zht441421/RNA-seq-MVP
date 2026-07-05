# Phase 1 Release Checklist

This checklist defines the release gate for the Phase 1 Bulk RNA-seq MVP.

## Supported Scope

Phase 1 supports:

- Bulk RNA-seq count matrix + metadata
- local file path registration for development and Coze-adapter simulation
- schema inspection and user-confirmed mapping
- QC and structured validation issues
- DESeq2 primary differential expression analysis
- edgeR / limma-voom validation when available
- docker_r as the recommended real analysis mode
- evidence package, reproducibility bundle, interpretation guardrails, and export package

## Unsupported Scope

Phase 1 does not support:

- single-cell RNA-seq
- spatial transcriptomics
- proteomics/metabolomics
- pathway enrichment automatic strong conclusions
- raw FASTQ alignment
- transcript quantification import
- clinical diagnosis
- MinIO/S3 production storage
- Nextflow or Snakemake
- production authentication or authorization

## Required Release Checks

Before a Phase 1 release candidate is accepted, run:

- `pytest`
- Docker image build/check for `bioinformatics-agent-r-bulk-rnaseq:0.1`
- docker_r smoke test
- Phase 1 acceptance script
- export package creation check
- replay dry-run check
- UI route check

Recommended commands:

```bash
pytest
python scripts/smoke_docker_r.py --base-url http://127.0.0.1:8001
python scripts/acceptance_phase_1.py --base-url http://127.0.0.1:8001
```

## Release Risks

- Small simulated datasets can trigger DESeq2 dispersion fallback.
- Docker Desktop and the R/Bioconductor image are required for docker_r.
- R package version pinning depends on the Docker image build.
- Result interpretation is intentionally limited to statistical signal review.
- Export packages archive evidence but do not validate biology.

## Strong Conclusion Limits

Strong scientific conclusions are gated by reliability grade and method status.

- Grades C, D, and E cannot support strong scientific conclusions.
- `primary_method_status=completed_with_warning` cannot be treated as grade A
  interpretation.
- Top genes must be described as candidate statistical signals, not mechanisms
  or causal drivers.
- The export package and acceptance report do not upgrade conclusion strength.

