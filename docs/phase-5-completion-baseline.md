# Phase 5 Completion Baseline

Phase 5 freezes the backend MVP integration baseline for Coze-ready Bulk
RNA-seq task execution. The baseline connects task lifecycle state, persistent
task metadata, safe input registration, minimal and gated DESeq2 execution,
task-scoped artifact access, Coze-facing result summaries, explicit contrast
direction, and a reproducible end-to-end demo.

This phase does not add new bioinformatics methods, frontend code, real Coze
API calls, Docker, Snakemake, Nextflow, database server dependencies, or
workflow engines.

## Completed Milestones

- Phase 5.1 persistent task storage: local SQLite persistence for task
  metadata, status, lifecycle events, artifact metadata, and task inputs.
- Phase 5.2 artifact download: safe task-scoped artifact download endpoint.
- Phase 5.3 Coze summary: structured task result summaries for Coze and
  front-end consumers.
- Phase 5.4 task input registration: safe task-scoped metadata/count-matrix
  registration under `BIOINFO_INPUT_ROOT`.
- Phase 5.5 contrast/reference control: explicit log2FC direction for
  `minimal_cpm_log2fc` and DESeq2.
- Phase 5.6 Coze-ready demo: reproducible backend demo that validates the
  registered-input minimal workflow, artifact downloads, and Coze summary.

## Current Endpoint List

- `GET /health`
- `POST /task/create`
- `POST /task/plan`
- `POST /task/qc`
- `POST /task/run`
- `GET /task/{task_id}/status`
- `GET /task/{task_id}/report`
- `GET /task/{task_id}/artifacts`
- `GET /task/{task_id}/artifacts/{artifact_name}/download`
- `GET /task/{task_id}/audit`
- `POST /task/validate-inputs`
- `GET /task/formal-de/preflight`
- `GET /task/{task_id}/coze-summary`
- `POST /task/{task_id}/inputs/register`

No new public endpoints are added by Phase 5.7.

## Current Supported Workflows

- `minimal_cpm_log2fc`: runs without R or DESeq2. Produces CPM normalization,
  preliminary log2FC ranking, QC summary, execution summary, manifest, and
  report artifacts.
- `deseq2`: runs only when `GET /task/formal-de/preflight` reports local
  R/Rscript/DESeq2 readiness. Produces DESeq2 results, summary, manifest,
  interpretation summary, and report artifacts.

edgeR, limma, enrichment analysis, batch correction, complex designs, and
frontend visualization are not implemented.

## Current Task Lifecycle

The deterministic lifecycle remains:

```text
created -> planned -> qc_placeholder_ready -> run_placeholder_ready
-> report_placeholder_ready -> artifacts_placeholder_ready
-> audit_placeholder_ready
```

Real minimal and DESeq2 run paths require the task to be
`qc_placeholder_ready` before `/task/run` marks it `run_placeholder_ready`.

## Current Storage Behavior

- Task records can be persisted in local SQLite.
- Lifecycle events are persisted with deterministic timestamps.
- Artifact metadata is persisted after runs and artifact listings.
- Registered input metadata is persisted with role, safe relative path, file
  size, and SHA-256 checksum.
- The storage layer is local development infrastructure, not a production
  database server.

## Current Input Behavior

- Clients can register `metadata` and `count_matrix` inputs with
  `POST /task/{task_id}/inputs/register`.
- Registered paths must be safe relative paths under `BIOINFO_INPUT_ROOT`.
- `/task/run` uses registered inputs when explicit `metadata_file` and
  `count_matrix_file` fields are omitted.
- If only one required input is registered, `/task/run` returns a deterministic
  validation error.
- No file upload endpoint is implemented.

## Current Artifact Behavior

- Generated artifacts are task-scoped under the configured output root.
- Artifact listings expose safe relative paths only.
- Artifact downloads require a known artifact name and task-scoped safe path.
- `GET /task/{task_id}/artifacts/{artifact_name}/download` does not expose
  arbitrary filesystem reads.

## Current Coze Summary Behavior

`GET /task/{task_id}/coze-summary` returns a safe structured summary with:

- `summary_message`
- `result_files`
- `download_links`
- `registered_inputs`
- `threshold_summary`
- `top_genes_by_padj`
- `top_genes_by_abs_log2fc`
- `contrast`
- `positive_log2fc_interpretation`
- `negative_log2fc_interpretation`
- `warnings`
- `limitations`
- `safe_to_present`

Minimal summaries remain exploratory and do not claim formal differential
expression statistics.

## Current Contrast Behavior

`POST /task/run` accepts:

- `contrast_column`
- `contrast_numerator`
- `contrast_denominator`

Current MVP support is limited to two-group `condition` contrasts. If the
contrast is omitted, the backend preserves deterministic first-seen metadata
ordering and records the contrast as inferred. Positive log2FC means higher
expression in the numerator relative to the denominator; negative log2FC means
lower expression in the numerator relative to the denominator.

## Current Demo Workflow

The backend demo command is:

```powershell
python scripts\run_phase_5_6_coze_ready_demo.py
```

It validates:

1. task creation
2. input registration
3. minimal `minimal_cpm_log2fc` execution with explicit contrast
4. task status fetch
5. artifact listing
6. `report.md` download
7. CSV artifact download
8. Coze summary fetch
9. public response safety checks

The demo uses `data/demo/rnaseq_minimal` and does not require R/Rscript/DESeq2.

## Current Safety Boundaries

- no absolute paths in public responses
- no arbitrary filesystem reads
- no traceback/token/password/secret leakage
- no internal R command leakage in validation errors
- no real Coze API calls
- no frontend code
- no workflow engine execution
- task artifact downloads are constrained to known task-scoped artifacts

## Current Limitations

- no frontend
- no real Coze API call
- no edgeR
- no limma
- no enrichment analysis
- no batch correction
- no complex design formulas
- no upload endpoint
- no production database server
- DESeq2 requires R/Rscript/DESeq2 preflight readiness
- minimal CPM/log2FC output is exploratory and not a formal DEG result

## Validation Commands

Run the Phase 5.7 completion baseline test:

```powershell
python -m pytest tests\test_phase_5_completion_baseline.py
```

Run the current Phase 5 integration regression suite:

```powershell
python -m pytest tests\test_task_plan_endpoint.py tests\test_task_qc_endpoint.py tests\test_task_run_endpoint.py tests\test_task_report_endpoint.py tests\test_task_artifacts_endpoint.py tests\test_task_audit_endpoint.py tests\test_task_lifecycle_placeholder_contract.py tests\test_task_error_contract.py tests\test_openapi_contract.py tests\test_phase_2_completion_baseline.py tests\test_task_registry_service.py tests\test_task_create_status_registry.py tests\test_task_lifecycle_registry_transitions.py tests\test_task_registry_transition_guards.py tests\test_task_registry_unknown_transitions.py tests\test_task_registry_unknown_read_endpoints.py tests\test_input_validation_service.py tests\test_task_validate_inputs_endpoint.py tests\test_artifact_paths_service.py tests\test_task_artifacts_output_contract.py tests\test_execution_adapter_service.py tests\test_task_run_execution_adapter.py tests\test_dry_run_execution_contract.py tests\test_execution_adapter_dry_run_files.py tests\test_rnaseq_minimal_service.py tests\test_task_run_minimal_rnaseq.py tests\test_task_artifacts_minimal_rnaseq.py tests\test_rnaseq_minimal_validation_errors.py tests\test_task_run_minimal_rnaseq_validation_errors.py tests\test_rnaseq_minimal_report_content.py tests\test_phase_4_4_demo_data.py tests\test_phase_4_4_demo_script.py tests\test_rnaseq_method_contract.py tests\test_task_run_formal_method_not_implemented.py tests\test_formal_de_preflight_service.py tests\test_formal_de_preflight_endpoint.py tests\test_deseq2_execution_service.py tests\test_task_run_deseq2_endpoint.py tests\test_task_artifacts_deseq2.py tests\test_deseq2_report_content.py tests\test_deseq2_interpretation_service.py tests\test_coze_response_contract_docs.py tests\test_phase_4_9_deseq2_demo_data.py tests\test_phase_4_9_deseq2_demo_script.py tests\test_phase_4_completion_baseline.py tests\test_task_store_sqlite.py tests\test_task_registry_persistence.py tests\test_task_persistent_lifecycle_endpoint.py tests\test_artifact_download_service.py tests\test_task_artifact_download_endpoint.py tests\test_coze_summary_service.py tests\test_task_coze_summary_endpoint.py tests\test_task_input_registration_service.py tests\test_task_input_registration_endpoint.py tests\test_contrast_validation_service.py tests\test_rnaseq_minimal_contrast_direction.py tests\test_task_run_contrast_contract.py tests\test_deseq2_contrast_contract.py tests\test_phase_5_6_coze_ready_demo_script.py tests\test_phase_5_6_coze_ready_demo_contract.py tests\test_phase_5_completion_baseline.py
```

Expected result: all tests pass, except the existing platform-specific skipped
test.

## Baseline Tag Plan

After review and validation, planned tags are:

- `phase-5-7-completion-baseline`
- `phase-5-mvp-integration-baseline`

Tags are intentionally not created by this implementation step.
