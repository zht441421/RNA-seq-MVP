# Phase 5 MVP Integration Checklist

Use this checklist to review the Phase 5 Coze-ready backend integration
baseline before tagging or starting Phase 6.

## API Endpoints

- [ ] `POST /task/create` creates deterministic task records.
- [ ] `POST /task/plan` advances tasks to planned.
- [ ] `POST /task/qc` advances tasks to QC-ready.
- [ ] `POST /task/run` supports placeholder, minimal, and gated DESeq2 paths.
- [ ] `GET /task/{task_id}/status` returns safe task status.
- [ ] `GET /task/{task_id}/artifacts` lists safe task-scoped artifacts.
- [ ] `GET /task/{task_id}/artifacts/{artifact_name}/download` downloads only
  known task-scoped artifacts.
- [ ] `GET /task/{task_id}/coze-summary` returns Coze-ready summaries.
- [ ] `POST /task/{task_id}/inputs/register` registers safe task input paths.

## Persistence

- [ ] Task metadata is persisted in local SQLite.
- [ ] Task status is persisted in local SQLite.
- [ ] Lifecycle events are persisted in local SQLite.
- [ ] Artifact metadata is persisted in local SQLite.
- [ ] Input registration metadata is persisted in local SQLite.
- [ ] Persistence remains local development infrastructure, not a production
  database server dependency.

## Input Registration

- [ ] Only `metadata` and `count_matrix` roles are accepted.
- [ ] Registered paths are safe relative paths under `BIOINFO_INPUT_ROOT`.
- [ ] Unsupported extensions are rejected.
- [ ] Absolute paths and traversal are rejected.
- [ ] `/task/run` can use registered inputs without explicit run file paths.

## Analysis Execution

- [ ] `minimal_cpm_log2fc` runs without R/Rscript/DESeq2.
- [ ] Minimal workflow remains exploratory and reports no formal statistical
  test.
- [ ] DESeq2 execution is gated by preflight readiness.
- [ ] DESeq2 requires local R/Rscript/DESeq2 availability.
- [ ] No edgeR, limma, enrichment, batch correction, or complex design is
  implemented.

## Contrast Direction

- [ ] `contrast_column`, `contrast_numerator`, and `contrast_denominator` are
  accepted by `POST /task/run`.
- [ ] Current MVP supports exactly two groups in `condition`.
- [ ] Explicit contrast direction is recorded in summaries and reports.
- [ ] Inferred contrast direction remains deterministic when explicit fields
  are omitted.
- [ ] Positive and negative log2FC interpretations are present.

## Artifact Generation

- [ ] Minimal workflow writes `run_manifest.json`.
- [ ] Minimal workflow writes `execution_summary.json`.
- [ ] Minimal workflow writes `qc_summary.json`.
- [ ] Minimal workflow writes `normalized_counts_cpm.csv`.
- [ ] Minimal workflow writes `differential_expression_results.csv`.
- [ ] Minimal workflow writes `report.md`.
- [ ] DESeq2 workflow writes DESeq2 result, summary, manifest,
  interpretation, and report artifacts when preflight is ready.

## Artifact Download Safety

- [ ] Downloaded artifacts must be known task artifacts.
- [ ] Artifact names reject absolute paths, traversal, separators, colons, and
  unsupported suffixes.
- [ ] Download links are relative API paths.
- [ ] Downloads do not expose arbitrary filesystem reads.
- [ ] Public payloads do not expose local absolute paths.

## Coze Summary Safety

- [ ] Coze summary includes `summary_message`.
- [ ] Coze summary includes `result_files`.
- [ ] Coze summary includes `download_links`.
- [ ] Coze summary includes `registered_inputs` when available.
- [ ] Coze summary includes `contrast` when available.
- [ ] Coze summary includes positive and negative log2FC interpretation.
- [ ] Coze summary includes warnings and limitations.
- [ ] Coze summary sets `safe_to_present` to the expected safe value.
- [ ] Coze summary avoids traceback/token/password/secret leakage.

## Demo Script

- [ ] `scripts/run_phase_5_6_coze_ready_demo.py` exists.
- [ ] The demo uses `data/demo/rnaseq_minimal`.
- [ ] The demo creates a task.
- [ ] The demo registers inputs.
- [ ] The demo runs `minimal_cpm_log2fc` with explicit contrast.
- [ ] The demo lists artifacts.
- [ ] The demo downloads `report.md`.
- [ ] The demo downloads a CSV artifact.
- [ ] The demo fetches `coze-summary`.
- [ ] The demo asserts public-response safety.

## OpenAPI Contract

- [ ] `docs/openapi.json` remains stable for Phase 5.7.
- [ ] No new public endpoint is added in the completion baseline.
- [ ] No request or response shape is changed in the completion baseline.
- [ ] `tests/test_openapi_contract.py` passes.

## Tests

- [ ] `tests/test_phase_5_completion_baseline.py` passes.
- [ ] Phase 5.6 demo script and contract tests pass.
- [ ] Artifact download tests pass.
- [ ] Coze summary tests pass.
- [ ] Task input registration tests pass.
- [ ] Contrast validation and contract tests pass.
- [ ] Main regression suite passes except the existing platform-specific skip.

## Security Boundaries

- [ ] no absolute paths in public responses
- [ ] no arbitrary filesystem reads
- [ ] no traceback/token/password/secret leakage
- [ ] no real Coze API calls
- [ ] no frontend code
- [ ] no workflow engine execution
- [ ] no production database server dependency

## Known Limitations

- [ ] no frontend
- [ ] no real Coze API call
- [ ] no edgeR
- [ ] no limma
- [ ] no enrichment analysis
- [ ] no batch correction
- [ ] no complex design formula
- [ ] no upload endpoint
- [ ] DESeq2 requires R/Rscript/DESeq2 readiness
- [ ] Minimal CPM/log2FC output is exploratory only

## Future Phase 6 Candidates

- [ ] Real external Coze integration or plugin packaging.
- [ ] Frontend workflow surface.
- [ ] Authn/authz and user/project ownership.
- [ ] Upload endpoint or object storage integration.
- [ ] Production task queue and production database plan.
- [ ] Richer QC/report UI once frontend exists.
- [ ] Optional DESeq2 demo path when preflight is ready.
- [ ] Expanded workflow support after separate method-design review.

## Tags

- [ ] `phase-5-7-completion-baseline`
- [ ] `phase-5-mvp-integration-baseline`

Tags are planned for release review and are not created by the checklist itself.
