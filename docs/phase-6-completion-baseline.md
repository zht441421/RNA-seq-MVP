# Phase 6 Completion Baseline

Phase 6 freezes the current backend as a deployment-readiness,
documentation, manifest-preparation, and local launch-verification baseline for
future Coze/API integration. It does not publish a Coze plugin, deploy a public
service, or change runtime behavior.

## Phase 6 Purpose

The purpose of Phase 6 is to make the existing Phase 5 backend contract
operable and reviewable before external exposure. The phase documents the
application entrypoint and API contract, prepares a narrow draft Coze/OpenAPI
subset, proves the current lifecycle through local HTTP, and provides an
operator runbook and checklist.

This completion baseline records those deliverables and freezes their current
scope. It adds documentation and deterministic validation only: no routes,
schemas, endpoint response shapes, analysis methods, or storage backends are
changed.

## Completed Phase 6 Milestones

- Phase 6.1 Coze API deployment contract: documents the FastAPI entrypoint,
  environment, endpoint sequence, request/response contract, example payloads,
  artifact behavior, and safety boundaries.
- Phase 6.2 Coze plugin / OpenAPI manifest preparation: provides draft plugin
  metadata, endpoint selection, field mappings, tool instructions, a generated
  Coze OpenAPI subset, and offline validation.
- Phase 6.3 local API smoke test / launch verification: starts a loopback
  Uvicorn process, exercises the task lifecycle over real local HTTP, validates
  summaries and downloads, and cleans up isolated state.
- Phase 6.4 deployment runbook / operator checklist: documents launch
  commands, bind behavior, storage operations, reverse-proxy controls, Coze
  base URL preparation, verification, troubleshooting, backup, and rollback.

## Current Deployment-Readiness Status

The backend is ready for controlled local launch and for deployment planning
behind a separately managed reverse proxy or API gateway. The application
entrypoint, environment variables, state layout, health check, one-worker
Uvicorn command, local smoke test, and operator procedures are documented and
covered by deterministic tests.

This is not a production-readiness claim. Authentication, authorization, TLS,
network access control, rate limits, request-size limits, monitoring, privacy,
retention, incident response, and public infrastructure remain
deployment-owner responsibilities.

## Current Coze/API Integration Readiness

Coze/API integration readiness is at the draft contract and preparation level:

- a reviewed task-oriented endpoint subset is available
- draft plugin metadata and tool instructions are available
- request/response examples and field mappings are available
- relative artifact download behavior is documented
- a future Coze base URL can be supplied outside the backend

The materials have not been published to Coze and no real Coze API has been
called. The Phase 6.2 narrow sequence also requires an integration review
because the current runtime lifecycle still needs the existing `POST
/task/plan` and `POST /task/qc` calls before `POST /task/run`.

## Current Local Launch Verification Status

Local launch verification is available through:

```powershell
python scripts\run_phase_6_3_local_api_smoke_test.py
```

The local smoke test starts `backend.app.main:app` on `127.0.0.1` with an
isolated port, input root, output root, and SQLite file. It verifies health,
task creation, input registration, plan/QC preparation, minimal execution,
status, artifacts, `coze-summary`, downloads, and public-response safety.

The smoke test is local-only. It does not validate public DNS, TLS, an external
reverse proxy, Coze credentials, or real Coze connectivity.

## Current Operator And Runbook Status

The deployment runbook is available at:

```text
docs/phase-6-4-deployment-runbook.md
```

The operator checklist is available at:

```text
docs/phase-6-4-operator-checklist.md
```

Together they cover environment and directory preparation, local and
reverse-proxy bind choices, health and smoke checks, input registration,
artifact/state operations, Coze base URL preparation, DESeq2 readiness,
logging, troubleshooting, backup/cleanup, rollback, and release tag
verification.

## Current Endpoint Sequence For Coze/API Use

The current executable lifecycle is:

1. `GET /health`
2. `POST /task/create`
3. `POST /task/{task_id}/inputs/register` for metadata
4. `POST /task/{task_id}/inputs/register` for the count matrix
5. `POST /task/plan`
6. `POST /task/qc`
7. `POST /task/run`
8. `GET /task/{task_id}/status`
9. `GET /task/{task_id}/artifacts`
10. `GET /task/{task_id}/coze-summary`
11. `GET /task/{task_id}/artifacts/{artifact_name}/download`

For DESeq2, call `GET /task/formal-de/preflight` before `POST /task/run` and
proceed only when readiness is true. The Phase 6.2 Coze subset remains a draft;
its narrower sequence does not silently remove the current plan and QC
prerequisites.

## Current Environment Variables

`BIOINFO_INPUT_ROOT`

: Root for trusted, pre-staged inputs. Clients register safe relative paths
  beneath this root.

`BIOINFO_OUTPUT_ROOT`

: Root for task-scoped generated artifacts.

`BIOINFO_TASK_STORE_PATH`

: Path to the local SQLite task store.

`BIOINFO_SMOKE_TEST_PORT`

: Optional loopback port override used only by the Phase 6.3 smoke test.

The first three settings are deployment-local implementation details and must
not appear in public API responses.

## Current Generated And Prepared Materials

Phase 6 freezes these materials:

- `docs/phase-6-1-api-deployment-contract.md`
- `docs/phase-6-1-coze-api-contract.md`
- `docs/examples/coze/` with deterministic example payloads and responses
- `docs/phase-6-2-coze-plugin-manifest-preparation.md`
- `docs/examples/coze_manifest/` with draft plugin and tool materials
- `docs/examples/coze_manifest/openapi_coze_subset.json`
- `scripts/run_phase_6_3_local_api_smoke_test.py`
- `docs/phase-6-3-local-api-smoke-test.md`
- `docs/phase-6-4-deployment-runbook.md`
- `docs/phase-6-4-operator-checklist.md`
- `docs/openapi.json` as the existing checked-in API schema

Phase 6.5 does not regenerate `docs/openapi.json`.

## Current Validation Commands

Validate the Phase 6 completion baseline:

```powershell
python -m pytest tests\test_phase_6_completion_baseline.py tests\test_phase_6_completion_baseline_script.py
python scripts\print_phase_6_completion_baseline.py
```

Validate the Phase 6.2 draft manifest materials and Phase 6.4 checklist:

```powershell
python scripts\validate_phase_6_2_coze_manifest.py
python scripts\print_phase_6_4_operator_checklist.py
```

Run the local HTTP launch verification:

```powershell
python scripts\run_phase_6_3_local_api_smoke_test.py
```

Run the current selected Phase 6 baseline regression suite:

```powershell
python -m pytest tests\test_task_plan_endpoint.py tests\test_task_qc_endpoint.py tests\test_task_run_endpoint.py tests\test_task_report_endpoint.py tests\test_task_artifacts_endpoint.py tests\test_task_audit_endpoint.py tests\test_task_lifecycle_placeholder_contract.py tests\test_task_error_contract.py tests\test_openapi_contract.py tests\test_phase_2_completion_baseline.py tests\test_task_registry_service.py tests\test_task_create_status_registry.py tests\test_task_lifecycle_registry_transitions.py tests\test_task_registry_transition_guards.py tests\test_task_registry_unknown_transitions.py tests\test_task_registry_unknown_read_endpoints.py tests\test_input_validation_service.py tests\test_task_validate_inputs_endpoint.py tests\test_artifact_paths_service.py tests\test_task_artifacts_output_contract.py tests\test_execution_adapter_service.py tests\test_task_run_execution_adapter.py tests\test_dry_run_execution_contract.py tests\test_execution_adapter_dry_run_files.py tests\test_rnaseq_minimal_service.py tests\test_task_run_minimal_rnaseq.py tests\test_task_artifacts_minimal_rnaseq.py tests\test_rnaseq_minimal_validation_errors.py tests\test_task_run_minimal_rnaseq_validation_errors.py tests\test_rnaseq_minimal_report_content.py tests\test_phase_4_4_demo_data.py tests\test_phase_4_4_demo_script.py tests\test_rnaseq_method_contract.py tests\test_task_run_formal_method_not_implemented.py tests\test_formal_de_preflight_service.py tests\test_formal_de_preflight_endpoint.py tests\test_deseq2_execution_service.py tests\test_task_run_deseq2_endpoint.py tests\test_task_artifacts_deseq2.py tests\test_deseq2_report_content.py tests\test_deseq2_interpretation_service.py tests\test_coze_response_contract_docs.py tests\test_phase_4_9_deseq2_demo_data.py tests\test_phase_4_9_deseq2_demo_script.py tests\test_phase_4_completion_baseline.py tests\test_task_store_sqlite.py tests\test_task_registry_persistence.py tests\test_task_persistent_lifecycle_endpoint.py tests\test_artifact_download_service.py tests\test_task_artifact_download_endpoint.py tests\test_coze_summary_service.py tests\test_task_coze_summary_endpoint.py tests\test_task_input_registration_service.py tests\test_task_input_registration_endpoint.py tests\test_contrast_validation_service.py tests\test_rnaseq_minimal_contrast_direction.py tests\test_task_run_contrast_contract.py tests\test_deseq2_contrast_contract.py tests\test_phase_5_6_coze_ready_demo_script.py tests\test_phase_5_6_coze_ready_demo_contract.py tests\test_phase_5_completion_baseline.py tests\test_phase_6_1_api_deployment_contract.py tests\test_phase_6_1_coze_examples.py tests\test_phase_6_2_coze_manifest_docs.py tests\test_phase_6_2_coze_manifest_examples.py tests\test_phase_6_2_coze_manifest_scripts.py tests\test_phase_6_3_local_api_smoke_test_script.py tests\test_phase_6_3_local_api_smoke_test_docs.py tests\test_phase_6_4_deployment_runbook_docs.py tests\test_phase_6_4_operator_checklist.py tests\test_phase_6_completion_baseline.py tests\test_phase_6_completion_baseline_script.py
```

## Current Expected Test Result

The expected result is that all selected tests pass, except the existing
platform-specific skipped test. The completion helper must print:

```text
Phase 6 deployment-readiness baseline verified
```

The helper is offline and does not start Uvicorn or another server.

## Safety Boundaries

- no arbitrary filesystem reads
- no public local absolute paths
- no traceback/token/password/secret leakage
- relative download URLs only
- local-only smoke test
- safe relative input registration beneath `BIOINFO_INPUT_ROOT`
- task-scoped artifact access beneath `BIOINFO_OUTPUT_ROOT`
- no runtime route, schema, or endpoint response-shape change in Phase 6.5

## Known Limitations

- no frontend
- no real Coze API publication yet
- no public deployment yet
- no edgeR
- no limma
- no enrichment analysis
- no upload endpoint
- no built-in production authentication or multi-node task coordination
- DESeq2 requires local R/Rscript/DESeq2 readiness, including BiocManager
- minimal CPM/log2FC output remains exploratory
- the draft Coze subset requires review of the current plan and QC lifecycle
  prerequisites before publication

## Phase 6 Final Baseline Scope

Phase 6 is complete at the deployment-readiness documentation, draft
plugin/manifest preparation, and local HTTP verification level. The Phase 5
runtime and scientific behavior remain unchanged. Future work must treat this
baseline as the reference point for any public exposure, real Coze
publication, authentication, upload/storage integration, concurrency, or new
analysis capabilities.

## Baseline Tag Plan

After review and validation, the planned baseline tags are:

- `phase-6-5-completion-baseline`
- `phase-6-deployment-readiness-baseline`

The existing Phase 6.1 through 6.4 tags remain historical milestones. The two
completion tags are intentionally not created by this implementation step.
