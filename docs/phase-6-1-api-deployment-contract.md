# Phase 6.1 API Deployment Contract

Phase 6.1 prepares the existing backend to be exposed later as a Coze-callable
API. It adds deployment documentation, machine-readable examples, and contract
tests only. It does not add routes, schemas, analysis methods, frontend code,
workflow engines, public hosting, Docker runtime requirements, or real Coze API
calls.

## Purpose

The purpose of this phase is to make the current backend contract clear enough
for a future reverse-proxied or hosted deployment. A Coze plugin or workflow can
be designed against the documented endpoint sequence, request payloads, response
shapes, artifact download behavior, and safety boundaries before real Coze
credentials or a public URL are available.

## Current Backend Entrypoint

The FastAPI application entrypoint is:

```text
backend.app.main:app
```

The current task lifecycle API is mounted under `/task`.

## Local Dev Startup Command

From the repository root, start the local development server with:

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The recommended local host and port are:

```text
http://127.0.0.1:8000
```

For a future private service behind a reverse proxy, the application may bind to
an internal interface chosen by the deployment platform, while the public URL is
terminated and protected by the proxy layer.

## Environment Variables

`BIOINFO_INPUT_ROOT`

: Root directory for task input registration. Clients submit safe relative
  paths under this root, such as `rnaseq_minimal/metadata.csv`. The API must not
  accept local absolute paths from Coze-facing payloads.

`BIOINFO_OUTPUT_ROOT`

: Root directory for generated task artifacts. Public responses expose
  task-scoped relative API download paths, not this local root.

`BIOINFO_TASK_STORE_PATH`

: SQLite file used for task metadata, lifecycle events, registered inputs, and
  artifact metadata. This is a local file dependency, not a database server
  dependency.

## Expected Directory Layout

The recommended local layout is:

```text
data/
  inputs/
  outputs/
  state/
```

- `data/inputs/` contains registered metadata and count matrix files.
- `data/outputs/` contains generated task artifacts under task-scoped
  subdirectories.
- `data/state/` contains the SQLite task store file.

These directories are deployment-local implementation details. Coze-facing
payloads and summaries should use safe relative paths and relative API download
paths.

## Minimal Workflow Runtime Requirements

The deterministic minimal workflow is `minimal_cpm_log2fc`. It requires:

- Python runtime with the repository dependencies installed.
- FastAPI and Uvicorn for serving the API.
- Readable metadata and count matrix files registered under
  `BIOINFO_INPUT_ROOT`.
- Writable output and state directories under `BIOINFO_OUTPUT_ROOT` and
  `BIOINFO_TASK_STORE_PATH`.

The minimal workflow does not require R, Rscript, BiocManager, DESeq2, Docker,
Snakemake, Nextflow, enrichment tooling, edgeR, or limma. It produces
exploratory CPM/log2FC rankings only and does not produce p-values or adjusted
p-values.

## DESeq2 Runtime Requirements

DESeq2 execution remains gated by the existing preflight check. A deployment
that wants to run `analysis_method: "deseq2"` must provide:

- R
- Rscript
- BiocManager
- DESeq2

The API should confirm readiness through:

```text
GET /task/formal-de/preflight
```

If preflight is not ready, `POST /task/run` for DESeq2 returns the existing
deterministic not-ready error and does not call Rscript.

## Safety Boundaries

Phase 6.1 preserves the current safety boundaries:

- no absolute paths in public responses
- no arbitrary filesystem reads
- no traceback/token/password/secret leakage
- registered inputs must stay under `BIOINFO_INPUT_ROOT`
- artifact downloads must stay under `BIOINFO_OUTPUT_ROOT`
- artifact download links are relative API paths only
- task store state uses SQLite only; no database server dependency is added
- no real Coze API call in this phase
- no public server is required in this phase

The backend must not expose local deployment paths such as input roots, output
roots, state files, shell command internals, or traceback text through
Coze-facing responses.

## Production Caveats

Before production exposure, a deployer still needs to add or configure:

- authentication and authorization
- request size and rate limits
- TLS termination
- audit and access logging policy
- task cleanup and retention policy
- input upload or object storage integration, if required
- operational monitoring
- a public URL only when the integration is ready to publish

These items are intentionally outside Phase 6.1. This phase documents the API
contract and local deployment shape without changing runtime behavior.

## Reverse Proxy And Public URL Notes

For a future Coze integration, a reverse proxy can expose the FastAPI backend
through a stable HTTPS base URL. The proxy should forward only intended API
paths, enforce authentication or allow-listing, and avoid serving local
directories directly.

The backend should continue to return relative paths such as:

```text
/task/task_0001/artifacts/report.md/download
```

The Coze plugin or deployment adapter can join that relative path with the
public API base URL outside the backend response. The backend itself should not
emit local absolute filesystem paths.

## Why Real Coze Credentials Are Not Required

This phase does not publish a Coze plugin, call Coze APIs, use Coze credentials,
or require a public server. The deliverable is the backend-side API deployment
contract: documented endpoint sequence, safe example payloads, and deterministic
tests that prepare the repository for later integration work.
