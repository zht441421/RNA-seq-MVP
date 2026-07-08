# Phase 3 Task Service Plan

## Phase 3.1 Goal

Phase 3.1 introduces an internal in-memory task registry for the existing
FastAPI task API. The goal is to make `POST /task/create` and
`GET /task/{task_id}/status` share a deterministic task record source while
preserving the Phase 2 API paths and placeholder analysis boundary.

This phase does not implement real RNA-seq analysis.
It also does not call real Coze services, run Snakemake, write log files, or
create real artifacts.

## In-Memory Registry Behavior

The registry lives in `backend/app/services/task_registry.py` and stores task
records in process memory. A created task record includes:

- `task_id`
- `project_name`
- `omics_type`
- `status`
- `created_at`
- `updated_at`
- `lifecycle_events`

Task IDs are deterministic within the current Python process and test run:

- `task_0001`
- `task_0002`
- `task_0003`

The registry has a reset helper for tests so each test can start from a known
counter and empty task set.

## Not Database Persistence

This registry is intentionally not database persistence. It is a small internal
service layer that helps define lifecycle behavior before durable storage,
queues, object storage, or production runners are introduced.

Task records are lost when the Python process exits or the server restarts.
There is no cross-process state sharing and no durable audit log.

## Current Create and Status Behavior

`POST /task/create` creates a task record in the in-memory registry and returns
the existing public response shape:

- `task_id`
- `status`
- `message`

The internal task record stores additional metadata, including project name,
omics type, timestamps, and lifecycle events. For compatibility, the public
response shape is not expanded in Phase 3.1.

When a task is created, the registry adds this lifecycle event:

```json
{
  "event_type": "task_created",
  "message": "Task record created in in-memory registry.",
  "actor": "system"
}
```

`GET /task/{task_id}/status` checks the same in-memory registry. If the task
exists, it returns the stored task status through the existing public response
shape. If the task does not exist, it returns a deterministic `404` response:

```json
{
  "detail": "Task not found: task_missing"
}
```

## Phase 3.2 Registry-Backed Placeholder Transitions

Phase 3.2 wires the existing `POST /task/plan`, `POST /task/qc`, and
`POST /task/run` placeholder endpoints to the in-memory registry lifecycle when
a request supplies a `task_id`.

The endpoints still return the existing placeholder response shapes. The
registry-backed behavior is:

- `POST /task/plan` with a known `task_id` updates the task status to
  `planned` and appends `plan_generated`.
- `POST /task/qc` with a known `task_id` updates the task status to
  `qc_placeholder_ready` and appends `qc_checked`.
- `POST /task/run` with a known `task_id` updates the task status to
  `run_placeholder_ready` and appends `run_placeholder_executed`.

`POST /task/plan` and `POST /task/qc` keep compatibility for requests that do
not include `task_id`: they return the same deterministic placeholder response
without mutating registry state. `POST /task/run` requires `task_id` as before.

If a request supplies a `task_id` that is not present in the registry, these
registry-backed transitions return a deterministic `404` response:

```json
{
  "detail": "Task not found: task_missing"
}
```

These transitions are process-local and in-memory only. They do not provide
durable persistence, a queue, a worker, artifact storage, or a durable audit
log. They also do not run real RNA-seq computation: no DESeq2, edgeR, limma,
FastQC, MultiQC, enrichment analysis, Snakemake, Nextflow, Coze service call, or
biological file I/O is performed.

`GET /task/{task_id}/status` now reflects the latest registry-backed status
after plan, QC, and run placeholder transitions.

## Phase 3.2b Strict Registry Transition Guard

Phase 3.2b adds a registry-level guard for the placeholder task lifecycle. The
only allowed in-memory status order is:

- `created` -> `planned`
- `planned` -> `qc_placeholder_ready`
- `qc_placeholder_ready` -> `run_placeholder_ready`
- `run_placeholder_ready` -> `report_placeholder_ready`
- `report_placeholder_ready` -> `artifacts_placeholder_ready`
- `artifacts_placeholder_ready` -> `audit_placeholder_ready`

`audit_placeholder_ready` is terminal. The registry rejects skipped steps,
rollbacks, repeated transitions, and attempts to move out of the terminal state
with a stable `Invalid task status transition` error. The registry does not
mutate `status`, `updated_at`, or `lifecycle_events` when a transition is
rejected.

The placeholder endpoints follow the same strict order when they receive a
known `task_id`: `POST /task/plan` must run before `POST /task/qc`, and
`POST /task/qc` must run before `POST /task/run`. Direct `created` -> QC or
`created` -> run requests return a deterministic `409` response. Unknown task
IDs continue to return the deterministic `404` response.

This guard is still only an in-memory placeholder contract. Status changes do
not mean that a real task executed. The API still does not call Coze, run
Snakemake, run an RNA-seq pipeline, write database records, write log files, or
create real artifacts. Future real execution still requires separately designed
controlled runner, worker, and persistence boundaries.

## Phase 3.3 Registry-Backed Report, Artifacts, and Audit Placeholders

Phase 3.3 wires the existing read-style placeholder endpoints to the same
in-memory task registry lifecycle while preserving the existing API paths and
public placeholder response shapes.

The registry-backed behavior is:

- `GET /task/{task_id}/report` with a known `task_id` updates the in-memory
  task status to `report_placeholder_ready` and appends
  `report_placeholder_generated`.
- `GET /task/{task_id}/artifacts` with a known `task_id` updates the in-memory
  task status to `artifacts_placeholder_ready` and appends
  `artifacts_placeholder_listed`.
- `GET /task/{task_id}/audit` with a known `task_id` returns the accumulated
  in-memory lifecycle events for that task through the existing audit response
  shape. It does not append an audit-viewed event, so repeated audit reads are
  deterministic and do not grow the lifecycle history.

If a request supplies a `task_id` that is not present in the registry, these
read endpoints return the same deterministic `404` response contract used by
the registry-backed transition endpoints:

```json
{
  "detail": "Task not found: task_missing"
}
```

The report and artifacts endpoints still return placeholder payloads only.
They do not generate durable report files, create artifact files, read
biological input files, run RNA-seq computation, or call Coze services. The
audit endpoint is also process-local and in-memory only. There is no durable
audit log, no database persistence, no real execution log reading, and no real
file generation.

## Phase 3.4 Input File Contract and Safe Path Validation Foundation

Phase 3.4 adds an internal input validation service for future RNA-seq
execution phases. The service lives in
`backend/app/services/input_validation.py` and defines the first safe file path
contract for metadata and count matrix inputs.

The input root is:

- `BIOINFO_INPUT_ROOT`, when the environment variable is set.
- `data/inputs`, relative to the project root, when the environment variable is
  not set.

The validation layer accepts relative paths only. It rejects:

- Empty paths.
- Paths containing null bytes.
- Absolute Windows paths such as `C:\...` or `D:\...`.
- Absolute Unix paths such as `/home/...` or `/mnt/...`.
- Path traversal such as `../` or `..\`.
- Resolved paths that escape the configured input root.
- Unsupported suffixes.

The allowed suffixes for the current RNA-seq placeholder contract are:

- `.csv`
- `.tsv`
- `.txt`

For Phase 3.4, validation checks path safety, suffixes, and file existence only.
It does not parse full file contents, validate biological schemas, read large
files, run QC, run DESeq2, edgeR, limma, FastQC, MultiQC, enrichment analysis,
Snakemake, Nextflow, or create report/artifact files.

Phase 3.4 also adds a minimal public endpoint:

- `POST /task/validate-inputs`

The endpoint validates `metadata_file` and `count_matrix_file` against the safe
input root. It returns `input_validation_completed`, a combined `valid` flag,
per-file suffix/existence/validity/errors, aggregate errors, and explicit
limitations. Public responses intentionally expose only safe input-root-relative
paths and do not expose local absolute filesystem paths.

This endpoint does not mutate the in-memory task registry and does not advance
the placeholder lifecycle. It is a deterministic preflight contract for future
execution work only.

## Phase 3.5 Artifact and Output Directory Contract Foundation

Phase 3.5 adds an internal artifact path service for future task outputs. The
service lives in `backend/app/services/artifact_paths.py` and defines where
future RNA-seq task outputs may be planned without generating real result
files.

The output root is:

- `BIOINFO_OUTPUT_ROOT`, when the environment variable is set.
- `data/outputs`, relative to the project root, when the environment variable
  is not set.

Task outputs are scoped under deterministic task directories:

```text
tasks/<task_id>/
```

The path layer rejects unsafe task IDs that are empty, contain null bytes,
contain slashes or backslashes, contain path traversal, or contain colons.
Safe task IDs such as `task_0001`, `task_demo`, and `task-abc_123` are accepted.

Artifact filenames must be single safe filenames. The path layer rejects
absolute artifact paths, nested paths, path traversal, null bytes, colons, and
unsupported suffixes. The allowed placeholder artifact suffixes are:

- `.json`
- `.csv`
- `.tsv`
- `.txt`
- `.md`
- `.html`
- `.png`
- `.pdf`

Phase 3.5 defines planned placeholder artifact specs for each task:

- `tasks/<task_id>/run_summary.json`
- `tasks/<task_id>/qc_summary.json`
- `tasks/<task_id>/differential_expression_results.csv`
- `tasks/<task_id>/report.md`

These paths are an output contract only. Phase 3.5 does not create biological
analysis files, fake result tables, report files, execution logs, or durable
artifact records. The only allowed filesystem creation in this phase is creating
the task output directory through the internal `ensure_task_output_dir()` helper
when a caller explicitly asks for it.

`GET /task/{task_id}/artifacts` now uses this planned artifact contract while
keeping the existing public response model. It exposes safe relative paths in
the existing `path` field and uses `available` to reflect whether a planned file
currently exists. It does not expose local absolute filesystem paths in public
responses and does not write any artifact files.

The execution adapter boundary is introduced in Phase 3.6 before any real
runner, queue, workflow engine, or RNA-seq computation is wired in.

## Phase 3.6 Execution Adapter Foundation

Phase 3.6 adds an internal execution adapter service for future RNA-seq task
execution. The service lives in `backend/app/services/execution_adapter.py` and
defines:

- `ExecutionRequest`
- `ExecutionResult`
- `ExecutorProtocol`
- `PlaceholderRNASeqExecutor`
- `get_executor()`
- `execute_task_placeholder()`

The placeholder executor name is `placeholder_rnaseq_executor`. It is
deterministic and returns fixed placeholder timing, planned artifact specs from
the Phase 3.5 artifact contract, messages, warnings, and limitations.

`POST /task/run` now calls the placeholder execution adapter after the
registry-backed transition to `run_placeholder_ready` succeeds. The endpoint
keeps the existing public response model and includes planned safe relative
artifact paths in the existing `artifacts` field. It does not expose local
absolute filesystem paths.

The placeholder executor may create the task-scoped output directory:

```text
tasks/<task_id>/
```

It does not create biological result files, report files, execution logs, or
database records. It also does not call external tools or services: no Rscript,
Docker, shell scripts, Snakemake, Nextflow, Coze service, DESeq2, edgeR, limma,
FastQC, MultiQC, or enrichment analysis is invoked.

The adapter is a boundary for future work only. Future Phase 3.7 should add
explicit dry-run execution behavior, and future Phase 4.1 should connect a real
minimal Bulk RNA-seq workflow only after validation, artifact, runner, and
persistence boundaries are designed and tested.

## Known Limitations

- No real RNA-seq execution is implemented.
- No DESeq2, edgeR, limma, FastQC, MultiQC, or enrichment analysis is wired.
- No real biological input/output files are read or written.
- No artifact files are created.
- No database persistence is implemented.
- No log files are written.
- No durable audit log is implemented.
- No real Coze service is called.
- No Snakemake workflow is run.
- Input validation checks path safety, allowed suffixes, and existence only; it
  does not parse file contents or validate RNA-seq schemas yet.
- Artifact path handling defines safe planned output locations only; it does
  not generate artifact files or real biological results.
- The execution adapter is placeholder-only; it may create the task output
  directory but does not generate real files or call external tools.

## Next Recommended Phases

- Add explicit dry-run execution behavior on top of the adapter interface.
- Connect a real minimal Bulk RNA-seq workflow only after the dry-run boundary
  is tested.
- Only later integrate real RNA-seq tools after state, validation, artifact,
  and execution adapter contracts are tested.
- Any production execution path must be designed separately with controlled
  runner, worker, and persistence boundaries.
