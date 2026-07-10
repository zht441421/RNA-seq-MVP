# Phase 6.3 Local API Smoke Test

Phase 6.3 adds a local API smoke test that launches the existing FastAPI
application and exercises it through real HTTP requests. It verifies the
Coze/plugin-oriented task sequence without changing API routes, schemas,
analysis algorithms, or endpoint response shapes.

## Purpose

The purpose of this phase is to prove that a fresh local process can start the
backend and complete the current task lifecycle over HTTP. This closes the gap
between in-process contract tests and a future deployed integration while
remaining deterministic, offline, and local-only.

## Relationship To Phases 6.1 And 6.2

Phase 6.1 documented the API deployment contract, including the application
entrypoint, environment variables, endpoint lifecycle, and response safety
boundaries. Phase 6.2 prepared draft Coze plugin metadata, endpoint selection,
and tool instructions for that same contract.

Phase 6.3 validates those preparations against a running local Uvicorn server.
The Phase 6.1 and 6.2 recommended sequence describes plan and QC as optional,
but the current backend state guard still requires those preparation states
before a run. The smoke test includes the existing calls and documents that
integration prerequisite; it does not change the guard. It also does not
publish the Phase 6.2 manifest or add a new public endpoint. There is no real Coze API call,
and no public deployment is required.

## What The Smoke Test Validates

The smoke test verifies that:

- the FastAPI application starts in a separate local server process
- `GET /health` becomes ready within a deterministic timeout
- a task can be created and both required inputs can be registered
- `minimal_cpm_log2fc` completes with an explicit contrast
- task status and generated artifacts are available after the run
- `coze-summary` is marked `safe_to_present`
- the contrast direction is present in the run artifacts and Coze summary
- `report.md` and a generated CSV artifact can be downloaded over HTTP
- public JSON, text, and download responses do not expose local paths,
  traceback text, or credential-like values
- artifact download links are relative API paths

These are real HTTP requests. The script does not use FastAPI `TestClient` and
does not require internet access.

## Run The Smoke Test

From the repository root, run:

```powershell
python scripts/run_phase_6_3_local_api_smoke_test.py
```

Expected success output is:

```text
Phase 6.3 local API smoke test passed
health verified
task created
inputs registered
run completed
status verified
artifacts verified
coze summary verified
downloads verified
```

The script exits with code `0` after all checks pass. On failure it prints a
concise deterministic failure message, exits non-zero, and still terminates the
local server process.

## Startup Behavior

The script starts `backend.app.main:app` with Uvicorn in a subprocess, binds it
only to `127.0.0.1`, and polls `GET /health` until the backend is ready or the
startup timeout expires. Requests are then sent to that loopback server using a
standard HTTP client rather than an in-process application client.

The port is deterministic by default and can be overridden with
`BIOINFO_SMOKE_TEST_PORT`. Test input, generated output, and SQLite state use
isolated locations supplied to the server subprocess. The Uvicorn subprocess is
terminated in cleanup whether the smoke test passes or fails.

## Environment Variables

`BIOINFO_SMOKE_TEST_PORT`

: Optional loopback port override for the temporary local server.

`BIOINFO_INPUT_ROOT`

: Isolated input root supplied to the server. The two bundled demo files are
  registered by safe relative paths beneath this root.

`BIOINFO_OUTPUT_ROOT`

: Isolated root for task-scoped generated artifacts. This local path must not
  appear in a public response.

`BIOINFO_TASK_STORE_PATH`

: Isolated SQLite task store used only for the smoke-test run. No database
  server is required.

These variables configure process-local test state; they do not widen the
public API's filesystem access boundary.

## Endpoint Sequence Tested

The required Phase 6.3 milestones run in this order:

1. `GET /health`
2. `POST /task/create`
3. `POST /task/{task_id}/inputs/register` for metadata
4. `POST /task/{task_id}/inputs/register` for the count matrix
5. `POST /task/run` with registered inputs and an explicit contrast
6. `GET /task/{task_id}/status`
7. `GET /task/{task_id}/artifacts`
8. `GET /task/{task_id}/coze-summary`
9. `GET /task/{task_id}/artifacts/report.md/download`
10. `GET /task/{task_id}/artifacts/differential_expression_results.csv/download`

The complete HTTP trace also includes `POST /task/plan` and `POST /task/qc`
between milestone 4 and milestone 5. The current backend lifecycle guard
requires the task to reach stored states `planned` and `qc_placeholder_ready`
before `POST /task/run`; input registration is a separate run prerequisite.
The QC endpoint response itself reports `qc_planned`. These two preparation
requests preserve the established state contract and do not add routes or
change response shapes. The ten numbered items above are the requested Phase
6.3 integration milestones.

The final two requests validate artifact download behavior for the Markdown
report and a generated CSV result. Downloads are requested through relative API
paths; local artifact paths are never returned to the client.

## Demo Data And Analysis Method

The smoke test uses the bundled deterministic demo data:

```text
data/demo/rnaseq_minimal/metadata.csv
data/demo/rnaseq_minimal/counts.csv
```

It runs `minimal_cpm_log2fc`, so R, Rscript, Bioconductor, and DESeq2 are not
required. The request supplies this explicit contrast:

```text
contrast_column = condition
contrast_numerator = treatment
contrast_denominator = control
```

Positive log2FC therefore means higher expression in `treatment` relative to
`control`. The smoke test verifies that this direction is represented in the
public result material.

## Local-Only Safety Boundary

The server listens on the loopback address only. The smoke test makes no real
Coze API call, makes no internet request, and requires no public deployment. It
does not expose arbitrary filesystem reads or convert local filesystem paths
into public download URLs.

Public JSON, text, and downloaded content are checked for path prefixes such as
Windows drive roots, `/home/`, `/mnt/`, and `file://`, as well as traceback and
credential-like terms. `coze-summary` must report `safe_to_present`, and every
download link must be a relative `/task/...` API path.

## Limitations

- This is a launch and integration smoke test, not a load, concurrency,
  security, or production-readiness test.
- The current task lifecycle still requires the existing plan and QC
  preparation calls before a run, although the Phase 6.1 and 6.2 recommended
  plugin sequence describes them as optional. A future integration must expose
  those calls or deliberately revise the state guard. Phase 6.3 does neither.
- It validates `minimal_cpm_log2fc`; it does not validate DESeq2 execution.
- The minimal result remains an exploratory CPM/log2FC ranking without formal
  p-values or adjusted p-values.
- It does not add edgeR, limma, enrichment analysis, frontend code, workflow
  engines, Docker requirements, authentication, or a database server.
- It does not validate a reverse proxy, TLS, public DNS, cloud storage, or Coze
  credentials.

## Future Deployment Notes

A future deployment can place the same FastAPI application behind a protected
HTTPS reverse proxy and join the relative artifact paths to an approved public
base URL. Before real Coze publishing, the deployment still needs
authentication and authorization, rate and request-size limits, retention and
cleanup policy, operational monitoring, secure upload or object storage where
needed, and deployment-specific manifest configuration.

Those production concerns remain outside Phase 6.3. The smoke test establishes
only that the existing contract can launch and complete its intended lifecycle
on a local loopback server.
