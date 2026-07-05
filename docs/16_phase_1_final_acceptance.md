# Phase 1 Final Acceptance

This document records the intended final acceptance path for Phase 1.0 through
Phase 1.13 of the Bulk RNA-seq MVP.

## Completed Phase Status

- Phase 1.0: project skeleton, FastAPI, schema, QC, plan, mock runner, reliability grading
- Phase 1.1: real_r runner and R differential expression script
- Phase 1.2: R/Bioconductor environment validation and small dataset smoke path
- Phase 1.3: evidence package and report system
- Phase 1.4: Dockerized R/Bioconductor runtime
- Phase 1.7: real Docker/R validation
- Phase 1.8: report and UI hardening
- Phase 1.9: input robustness and user error recovery
- Phase 1.10: reproducibility bundle and replay dry-run
- Phase 1.11: result interpretation guardrails
- Phase 1.12: project export package
- Phase 1.13: end-to-end acceptance suite and release hardening, validated

## Final Acceptance Commands

Run unit and integration tests:

```bash
pytest
```

Start FastAPI in docker_r mode:

```bash
set RUN_MODE=docker_r
set DOCKER_R_IMAGE=bioinformatics-agent-r-bulk-rnaseq:0.1
uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

Run docker_r smoke:

```bash
python scripts/smoke_docker_r.py --base-url http://127.0.0.1:8001
```

Run the final acceptance suite:

```bash
python scripts/acceptance_phase_1.py --base-url http://127.0.0.1:8001
```

The acceptance script writes:

```text
acceptance_reports/phase_1_acceptance_<timestamp>.json
acceptance_reports/phase_1_acceptance_<timestamp>.md
```

Latest local validation in this workspace:

```text
acceptance_reports/phase_1_acceptance_20260705T062732Z.json
acceptance_reports/phase_1_acceptance_20260705T062732Z.md
```

The latest report recorded `overall_status=passed`, mock reliability grade C,
docker_r reliability grade B, bad input smoke passed, replay dry-run passed, and
export package creation passed.

## Required Acceptance Evidence

The acceptance report should record:

- system health
- docker_r availability
- mock smoke project ID
- docker_r smoke project ID, when Docker is ready
- final statuses
- reliability grades
- key artifacts present
- bad input validation smoke result
- replay dry-run result
- export package path and SHA256
- UI route check
- warnings and failures
- overall status

## Release Boundary

Phase 1 supports only Bulk RNA-seq count matrix + metadata. It does not support
single-cell RNA-seq, spatial transcriptomics, proteomics/metabolomics, raw FASTQ
alignment, clinical diagnosis, or automatic pathway-level strong conclusions.

Acceptance means the workflow and audit package are operational. It does not
mean every future dataset will receive grade A or B, and it does not override
the reliability grade or interpretation guardrails.
