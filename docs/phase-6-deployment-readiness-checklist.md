# Phase 6 Deployment-Readiness Checklist

Use this checklist to verify that Phase 6 is frozen at the documented,
draft-integration, and local HTTP validation level. Record evidence for every
checked item. This checklist does not authorize public deployment or real Coze
publication.

## Phase 6.1 Deployment And API Contract

- [ ] `docs/phase-6-1-api-deployment-contract.md` exists and identifies
  `backend.app.main:app`.
- [ ] `docs/phase-6-1-coze-api-contract.md` exists and documents the current
  task lifecycle.
- [ ] The local startup command uses Uvicorn and a controlled bind.
- [ ] The contract preserves existing endpoint request and response shapes.
- [ ] Input and artifact path boundaries are documented.

## Phase 6.2 Plugin And Manifest Materials

- [ ] `docs/phase-6-2-coze-plugin-manifest-preparation.md` exists.
- [ ] `docs/examples/coze_manifest/` contains the draft plugin metadata,
  endpoint selection, field mapping, tool instructions, and tool sequence.
- [ ] The Coze OpenAPI subset is available at
  `docs/examples/coze_manifest/openapi_coze_subset.json`.
- [ ] `python scripts/validate_phase_6_2_coze_manifest.py` passes.
- [ ] All plugin and manifest materials remain identified as draft preparation
  files.

## Phase 6.3 Local HTTP Smoke Test

- [ ] `scripts/run_phase_6_3_local_api_smoke_test.py` exists.
- [ ] `docs/phase-6-3-local-api-smoke-test.md` exists.
- [ ] The local HTTP smoke test binds to `127.0.0.1` and uses isolated state.
- [ ] The smoke test passes without an internet request or public service.
- [ ] Health, lifecycle, artifacts, `coze-summary`, and downloads are verified.

## Phase 6.4 Deployment Runbook And Operator Checklist

- [ ] `docs/phase-6-4-deployment-runbook.md` exists.
- [ ] `docs/phase-6-4-operator-checklist.md` exists.
- [ ] `python scripts/print_phase_6_4_operator_checklist.py` passes.
- [ ] Launch, reverse-proxy controls, Coze base URL preparation, storage,
  diagnostics, troubleshooting, backup, cleanup, and rollback are documented.
- [ ] The current plan and QC prerequisites are treated as an integration gate.

## OpenAPI And Example Availability

- [ ] The checked-in OpenAPI document exists at `docs/openapi.json`.
- [ ] The Coze OpenAPI subset contains only the reviewed draft endpoint
  selection.
- [ ] Example payloads are available under `docs/examples/coze/`.
- [ ] Examples cover task creation, input registration, minimal and DESeq2
  requests, summary output, downloads, and safe errors.
- [ ] Phase 6.5 did not regenerate or modify `docs/openapi.json`.

## Local Startup And Environment

- [ ] Local development startup is documented as:

  ```powershell
  uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
  ```

- [ ] Stable operator launch uses one Uvicorn worker and omits reload.
- [ ] `BIOINFO_INPUT_ROOT` identifies the trusted input root.
- [ ] `BIOINFO_OUTPUT_ROOT` identifies the task-artifact root.
- [ ] `BIOINFO_TASK_STORE_PATH` identifies the local SQLite state file.
- [ ] `BIOINFO_SMOKE_TEST_PORT` is used only as an optional local smoke-test
  port override.
- [ ] The health check `GET /health` returns the expected service identity.

## Input Registration And Explicit Contrast

- [ ] Metadata and count matrix inputs are pre-staged beneath the configured
  input root.
- [ ] `POST /task/{task_id}/inputs/register` accepts safe relative paths only.
- [ ] Both required input roles are registered before execution.
- [ ] `contrast_column`, `contrast_numerator`, and `contrast_denominator` are
  supplied from approved metadata when an explicit contrast is requested.
- [ ] Positive and negative log2FC direction is represented consistently in
  results and summaries.
- [ ] The current `POST /task/plan` and `POST /task/qc` calls occur before
  `POST /task/run`.

## Artifact Download And Coze-Summary Safety

- [ ] `GET /task/{task_id}/artifacts` lists task-scoped artifacts.
- [ ] Artifact download uses
  `GET /task/{task_id}/artifacts/{artifact_name}/download`.
- [ ] Artifact download links are relative `/task/...` API paths.
- [ ] Unknown tasks and artifacts return the existing safe error shape.
- [ ] `GET /task/{task_id}/coze-summary` uses safe relative registered inputs
  and download links.
- [ ] Minimal results retain exploratory CPM/log2FC limitations.
- [ ] Public responses omit internal filesystem locations, process details,
  and credential material.

## DESeq2 Preflight Caveat

- [ ] `GET /task/formal-de/preflight` is called before a DESeq2 request.
- [ ] R, Rscript, BiocManager, and DESeq2 are available when DESeq2 is enabled.
- [ ] A not-ready response blocks the DESeq2 run and any DESeq2 completion
  claim.
- [ ] `minimal_cpm_log2fc` remains usable without the optional R runtime.

## Release Tags

- [ ] `phase-6-1-coze-api-deployment-contract` identifies the reviewed 6.1
  milestone.
- [ ] `phase-6-2-coze-plugin-manifest-preparation` identifies the reviewed 6.2
  milestone.
- [ ] `phase-6-3-local-api-smoke-test` identifies the reviewed 6.3 milestone.
- [ ] `phase-6-4-deployment-runbook` identifies the reviewed 6.4 milestone.
- [ ] The planned completion tags are
  `phase-6-5-completion-baseline` and
  `phase-6-deployment-readiness-baseline`.
- [ ] No completion tag is created by the Phase 6.5 implementation step.

## Known Limitations

- [ ] No frontend is included.
- [ ] No real Coze API publication is included.
- [ ] No public deployment is included.
- [ ] No edgeR implementation is included.
- [ ] No limma implementation is included.
- [ ] No enrichment analysis is included.
- [ ] No Docker runtime, workflow engine, or database server is required.
- [ ] DESeq2 depends on local R runtime readiness.
- [ ] The draft Coze sequence requires the current plan and QC calls.

## Future Phase 7 Candidates

These are candidates for separate review, not Phase 6.5 commitments:

- [ ] production authentication and authorization design
- [ ] protected public deployment and real Coze publication
- [ ] reviewed upload or object-storage integration
- [ ] task queue and multi-process coordination
- [ ] operational metrics, alerting, retention automation, and incident
  response
- [ ] proxy, TLS, rate, request-size, load, and concurrency validation
- [ ] deliberate reconciliation of the draft Coze subset with plan/QC runtime
  prerequisites

Any future Phase 7 change must preserve the frozen safety and scientific
interpretation boundaries unless a separately reviewed contract explicitly
replaces them.
