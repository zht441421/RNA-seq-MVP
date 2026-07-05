# Phase 1.8 Report/UI Hardening

Phase 1.8 improves report visibility, local UI artifact review, and audit
readability for real Bulk RNA-seq runs.

This phase does not change:

- Bulk RNA-seq analysis logic.
- DESeq2, edgeR, or limma-voom statistical workflow.
- Docker image contents or Dockerfile.
- Reliability grading rules.
- Evidence package directory structure.
- Coze adapter workflow semantics.

## What Changed

The local `/ui` workflow now includes an Artifact Review area after Get Report.
It shows:

- final status
- reliability grade
- `strong_conclusion_allowed`
- `primary_method_status`
- `validation_consistency_score`
- warnings
- errors
- key artifact status summary
- full manifest artifact list

The `/coze/projects/{project_id}/report` and `/projects/{project_id}/results`
responses now expose the same review-oriented fields in a backward-compatible
way. Existing response fields remain available.

## completed_with_warning Display

Real DESeq2 runs may complete with a warning when the standard dispersion fit
fails and the runner uses gene-wise dispersion fallback. In that case:

```text
primary_method_status = completed_with_warning
```

The UI displays:

```text
主分析已完成，但存在方法学 warning，请谨慎解释结果。
```

The warning is also visible in `run_status.json`, report responses, and the
artifact review panel.

`completed_with_warning` can still produce DESeq2, edgeR, limma-voom, and
validation comparison artifacts, but it is capped below reliability grade A.

## Strong Conclusion Display

When `strong_conclusion_allowed=false`, the UI displays:

```text
当前证据不足以支持强科研结论。
```

Grades C, D, and E remain limited by the existing reliability rules. Phase 1.8
does not relax those boundaries.

## Artifact Review

The UI highlights these key artifacts:

- `04_main_results/deseq2_results.csv`
- `05_validation_results/edger_results.csv`
- `05_validation_results/limma_voom_results.csv`
- `05_validation_results/validation_comparison.csv`
- `09_environment/run_status.json`
- `09_environment/r_session_info.txt`
- `10_audit_log.json`
- `11_reliability_report.md`
- `manifest.json`

If no artifact download endpoint is available, the UI shows relative paths and
manifest status only.

## What Users Should Inspect

For a real `docker_r` run, review:

1. `manifest.json` for `present`, `missing`, and `not_applicable` artifact
   states.
2. `09_environment/run_status.json` for primary method status, validation
   status, warnings, errors, and validation consistency.
3. `11_reliability_report.md` for reliability rationale and downgrade
   conditions.
4. `05_validation_results/validation_comparison.csv` for direction consistency
   across validation methods.
5. `10_audit_log.json` for inputs, method configuration, run mode, package
   versions, and environment references.

## Validation

Expected validation commands:

```bash
pytest
python scripts/smoke_docker_r.py --base-url http://127.0.0.1:8000
```

The docker smoke test should remain completed and should continue to produce
real artifacts through the Dockerized R/Bioconductor runtime.

