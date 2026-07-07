# Phase 2 API Contract Baseline Completion

## Summary

Phase 2 establishes a deterministic FastAPI placeholder API contract for
Coze and front-end integration. The API shape, core endpoint paths, expected
methods, placeholder response boundaries, error behavior, and OpenAPI schema
visibility are now documented and covered by focused contract tests.

Phase 2 does not execute real RNA-seq analysis. It does not run DESeq2, edgeR,
limma, QC computation, report generation, artifact generation, or durable task
persistence. The current API is a stable integration baseline, not a production
analysis backend.

## Completed Endpoint Inventory

| Endpoint | Purpose | Current status | Placeholder-only | Tests |
| --- | --- | --- | --- | --- |
| `GET /health` | Confirms the FastAPI service is reachable and identifies the skeleton phase. | Implemented as a deterministic service health response. | No, this is a lightweight service check. | Covered by `tests/test_openapi_contract.py` for path and method visibility. |
| `POST /task/create` | Creates a task identifier for integration flow sampling. | Implemented with in-memory placeholder task creation. | Yes. It does not persist to a database or start execution. | Covered by `tests/test_openapi_contract.py` for path and method visibility. |
| `GET /task/{task_id}/status` | Returns status for a previously created in-memory placeholder task. | Implemented for current in-memory task service behavior. | Yes. Task state is not durable. | Covered by `tests/test_openapi_contract.py` for path and method visibility. |
| `POST /task/plan` | Returns a deterministic analysis planning response for a submitted task request. | Implemented as a placeholder planning contract. | Yes. It does not run a real planning engine or analysis tools. | Covered by `tests/test_task_plan_endpoint.py`, `tests/test_task_lifecycle_placeholder_contract.py`, `tests/test_task_error_contract.py`, and `tests/test_openapi_contract.py`. |
| `POST /task/qc` | Returns deterministic QC planning checks and reliability gates. | Implemented as a placeholder QC contract. | Yes. It does not read metadata, count matrices, or compute QC metrics. | Covered by `tests/test_task_qc_endpoint.py`, `tests/test_task_lifecycle_placeholder_contract.py`, `tests/test_task_error_contract.py`, and `tests/test_openapi_contract.py`. |
| `POST /task/run` | Returns deterministic placeholder run steps for integration testing. | Implemented as a run placeholder response. | Yes. It does not read or write files and does not run RNA-seq tools. | Covered by `tests/test_task_run_endpoint.py`, `tests/test_task_lifecycle_placeholder_contract.py`, `tests/test_task_error_contract.py`, and `tests/test_openapi_contract.py`. |
| `GET /task/{task_id}/report` | Returns a deterministic placeholder report payload for a task ID. | Implemented as a placeholder report response. | Yes. It does not generate a report file or produce biological conclusions. | Covered by `tests/test_task_report_endpoint.py`, `tests/test_task_lifecycle_placeholder_contract.py`, `tests/test_task_error_contract.py`, and `tests/test_openapi_contract.py`. |
| `GET /task/{task_id}/artifacts` | Returns deterministic placeholder artifact metadata for a task ID. | Implemented as a placeholder artifact list. | Yes. It does not create, read, serve, or download real artifact files. | Covered by `tests/test_task_artifacts_endpoint.py`, `tests/test_task_lifecycle_placeholder_contract.py`, `tests/test_task_error_contract.py`, and `tests/test_openapi_contract.py`. |
| `GET /task/{task_id}/audit` | Returns deterministic placeholder audit events for a task ID. | Implemented as a placeholder audit trail. | Yes. It does not read or write durable audit history. | Covered by `tests/test_task_audit_endpoint.py`, `tests/test_task_lifecycle_placeholder_contract.py`, `tests/test_task_error_contract.py`, and `tests/test_openapi_contract.py`. |
| `GET /openapi.json` | Exposes the generated FastAPI OpenAPI schema for Coze/plugin integration planning. | Implemented by FastAPI and contract-tested for current paths and methods. | No, this is schema visibility for the placeholder API contract. | Covered by `tests/test_openapi_contract.py`. |

## Test Inventory

- `tests/test_task_plan_endpoint.py` validates the `/task/plan` placeholder
  response shape, deterministic planning content, and current no-real-analysis
  boundary.
- `tests/test_task_qc_endpoint.py` validates the `/task/qc` placeholder QC
  checks, reliability gates, limitations, and deterministic response contract.
- `tests/test_task_run_endpoint.py` validates the `/task/run` placeholder run
  response, run step contract, empty artifact behavior, and no-real-execution
  boundary.
- `tests/test_task_report_endpoint.py` validates the
  `/task/{task_id}/report` placeholder report sections, task ID echo, and
  limitation messaging.
- `tests/test_task_artifacts_endpoint.py` validates the
  `/task/{task_id}/artifacts` placeholder artifact inventory and confirms
  artifacts are not currently real files.
- `tests/test_task_audit_endpoint.py` validates the `/task/{task_id}/audit`
  placeholder audit event list, deterministic metadata, and durable-storage
  limitations.
- `tests/test_task_lifecycle_placeholder_contract.py` validates that the
  Phase 2 placeholder lifecycle endpoints remain bounded, deterministic, and
  consistent when using a shared task ID.
- `tests/test_task_error_contract.py` validates stable validation and routing
  error behavior, including that error payloads do not expose local paths or
  sensitive fragments.
- `tests/test_openapi_contract.py` validates `GET /openapi.json`, required
  schema keys, all current endpoint paths, expected HTTP methods, and forbidden
  schema text fragments.

## OpenAPI Baseline

FastAPI exposes the live schema at `GET /openapi.json`.

The file `docs/openapi.json` is a deterministic exported schema snapshot for
the current Phase 2 API contract. It is useful for Coze/plugin integration
review, contract diffs, and front-end planning without starting the server.

The script `scripts/export_openapi_schema.py` regenerates the snapshot by
importing `backend.app.main:app` and writing `app.openapi()` to
`docs/openapi.json` with UTF-8 JSON and `indent=2`. It does not require server
startup.

## Known Placeholder Limitations

- No real RNA-seq execution yet.
- No DESeq2/edgeR/limma execution yet.
- No real QC computation yet.
- No real report file generation yet.
- No real artifact files yet.
- No database persistence yet.
- No durable audit log yet.
- Some task lifecycle responses do not yet share a persisted task state.

## Phase 3 Recommended Direction

Phase 3 should prepare real execution through safe incremental steps:

- Create an internal task service layer that owns lifecycle transitions and
  response construction.
- Introduce a deterministic local task registry or in-memory state first,
  before adding durable storage.
- Define the input file validation contract, including accepted file roles,
  metadata requirements, count matrix expectations, and validation errors.
- Define the output artifact directory contract, including naming, manifest
  shape, retention boundaries, and download/readback behavior.
- Add a controlled execution adapter interface so the API can call mock,
  dry-run, local, Docker, or future production runners through the same
  boundary.
- Only later wire real RNA-seq tools after the state, validation, artifact, and
  execution adapter contracts are tested.

## Operational Commands

Enter the correct working directory:

```powershell
cd "<repo-root>"
```

Replace `<repo-root>` with your local checkout path.

Run the Phase 2 completion baseline documentation test:

```powershell
python -m pytest tests\test_phase_2_completion_baseline.py
```

Run the full Phase 2 API contract test suite:

```powershell
python -m pytest tests\test_task_plan_endpoint.py tests\test_task_qc_endpoint.py tests\test_task_run_endpoint.py tests\test_task_report_endpoint.py tests\test_task_artifacts_endpoint.py tests\test_task_audit_endpoint.py tests\test_task_lifecycle_placeholder_contract.py tests\test_task_error_contract.py tests\test_openapi_contract.py tests\test_phase_2_completion_baseline.py
```

Export the OpenAPI schema snapshot:

```powershell
python scripts\export_openapi_schema.py
```

Check git status:

```powershell
git status --short
```
