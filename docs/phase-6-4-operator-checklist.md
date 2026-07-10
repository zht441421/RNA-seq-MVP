# Phase 6.4 Operator Checklist

Use this checklist with
`docs/phase-6-4-deployment-runbook.md`. Record the revision, environment,
operator, time, evidence, and outcome for every launch or exposure review.
Unchecked items remain release blockers unless a named owner records a
separate decision.

## Before Launch

- [ ] The reviewed application revision is recorded.
- [ ] The Phase 6.1 deployment contract, Phase 6.2 draft plugin materials,
  Phase 6.3 local smoke test, and Phase 6.4 runbook were reviewed.
- [ ] `python -m pip install -r requirements.txt` completed in the intended
  Python environment.
- [ ] The requested deterministic test suites passed.
- [ ] No runtime, route, schema, analysis, or public response-shape change is
  included in this release.

## Environment Variables

- [ ] `BIOINFO_INPUT_ROOT` identifies the trusted input root.
- [ ] `BIOINFO_OUTPUT_ROOT` identifies the writable task-artifact root.
- [ ] `BIOINFO_TASK_STORE_PATH` identifies the writable local SQLite file.
- [ ] The recorded values belong to the intended environment.
- [ ] Staging and production do not share one state or output location.

## Directory Existence

- [ ] `data/inputs/` or the configured input root exists and is readable.
- [ ] `data/outputs/` or the configured output root exists and is writable.
- [ ] `data/state/` or the configured state parent exists and is writable.
- [ ] Input, output, state, repository, and log directories are not served as
  static content.
- [ ] Free space is sufficient for the planned task and retention window.

## Local-Only Launch

- [ ] Local development uses:

  ```powershell
  uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
  ```

- [ ] Stable local validation omits reload and uses one worker.
- [ ] A same-host reverse proxy keeps the Uvicorn upstream on `127.0.0.1`.
- [ ] Any private-network bind is restricted to the controlled proxy or
  platform.
- [ ] The Uvicorn port is not directly reachable from an untrusted network.

## Health Check

- [ ] `GET /health` returns HTTP 200.
- [ ] The response reports `status` as `ok`.
- [ ] The response identifies `bioinformatics-agent-backend`.
- [ ] Health was checked on the local upstream before proxy checks.
- [ ] Health success was not treated as proof of workflow or security
  readiness.

## Smoke Test

- [ ] This command completed successfully:

  ```powershell
  python scripts/run_phase_6_3_local_api_smoke_test.py
  ```

- [ ] The output begins with `Phase 6.3 local API smoke test passed`.
- [ ] The operator understands that the smoke test uses isolated local state
  and does not validate an external proxy or Coze connectivity.

## Coze Base URL Readiness

- [ ] One stable HTTPS Coze base URL is recorded for the future reviewed
  publication step.
- [ ] TLS, authentication, authorization, endpoint allow-listing, rate limits,
  request-size limits, and timeouts are provided by the controlled gateway.
- [ ] The base URL routes only approved API paths to the private upstream.
- [ ] `GET /health` works through the base URL for an authorized client.
- [ ] The current `POST /task/plan` and `POST /task/qc` prerequisites are
  included in the reviewed client sequence before `POST /task/run`.
- [ ] Public deployment and Coze publication remain blocked until all exposure
  controls and lifecycle calls are approved.

## Artifact Download Verification

- [ ] `GET /task/{task_id}/artifacts` lists only task-scoped entries.
- [ ] `GET /task/{task_id}/artifacts/{artifact_name}/download` returns an
  approved artifact.
- [ ] Artifact download links remain relative `/task/...` API paths.
- [ ] An unknown artifact returns the existing safe not-found response.
- [ ] The output root is not directly mapped by the reverse proxy.

## Coze-Summary Verification

- [ ] `GET /task/{task_id}/coze-summary` returns the expected task identifier.
- [ ] `safe_to_present` follows the existing result rules.
- [ ] Registered inputs are represented by safe relative paths.
- [ ] Contrast direction and method limitations are present.
- [ ] Minimal results are described as exploratory CPM/log2FC output.
- [ ] Download links match the reviewed task artifacts.

## Safety Verification

- [ ] Input registration rejects absolute and traversal paths.
- [ ] No arbitrary filesystem reads are available.
- [ ] Public responses contain no local absolute paths.
- [ ] Download URLs are relative API paths only.
- [ ] Public errors contain no internal stack details, credential material, or
  process environment values.
- [ ] Operator logs are access-controlled, retained, and redacted.
- [ ] Input, output, and state directories cannot be browsed through the
  public API or proxy.

## DESeq2 Preflight Check

- [ ] The deployment decision records whether DESeq2 is enabled.
- [ ] If enabled, R, Rscript, BiocManager, and DESeq2 are available.
- [ ] `GET /task/formal-de/preflight` reports ready before a DESeq2 request.
- [ ] A not-ready preflight blocks DESeq2 claims and runs.
- [ ] `minimal_cpm_log2fc` remains available without the optional R runtime.

## Backup And Cleanup

- [ ] The SQLite file and matching output root have a consistent backup plan.
- [ ] Writes are drained before a state-and-artifact backup or restore.
- [ ] Retention duration and cleanup ownership are recorded.
- [ ] Cleanup is task-scoped and does not remove unrelated inputs or outputs.
- [ ] Restore steps have been reviewed without modifying API behavior.

## Troubleshooting

- [ ] Service-start failures are investigated from the repository root and the
  intended Python environment.
- [ ] Port ownership and proxy upstream configuration are checked together.
- [ ] Missing inputs are staged beneath the configured input root.
- [ ] Unsafe paths are corrected to safe relative paths without relaxing
  validation.
- [ ] Invalid contrast values are corrected from approved metadata.
- [ ] Artifact not-found errors are checked against task state and the output
  root.
- [ ] SQLite locking returns the deployment to one process and one worker.
- [ ] DESeq2 not-ready results keep the optional method disabled.
- [ ] Any public-response safety failure removes external traffic until
  reviewed and corrected.

## Known Limitations

- [ ] No frontend is included.
- [ ] No real Coze API publication yet is included.
- [ ] No public deployment is required by Phase 6.4.
- [ ] No edgeR implementation is included.
- [ ] No limma implementation is included.
- [ ] No enrichment analysis is included.
- [ ] No Docker runtime, workflow engine, or database server is required.
- [ ] DESeq2 depends on local R runtime readiness.
- [ ] The current lifecycle still needs plan and QC preparation calls.

## Release Tag Verification

- [ ] `phase-6-1-coze-api-deployment-contract` resolves to the reviewed Phase
  6.1 baseline.
- [ ] `phase-6-2-coze-plugin-manifest-preparation` resolves to the reviewed
  Phase 6.2 baseline.
- [ ] `phase-6-3-local-api-smoke-test` resolves to the reviewed Phase 6.3
  baseline.
- [ ] The rollback plan identifies a previously validated Git tag and its
  commit.
- [ ] No new Phase 6.4 Git tag is created by this documentation-only phase.
- [ ] After rollback, the service is restarted and health, manifest, smoke, and
  state/artifact checks are repeated before traffic reopens.
