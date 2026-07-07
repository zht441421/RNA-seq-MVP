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
- `POST /task/plan`, `POST /task/qc`, `POST /task/run`,
  `GET /task/{task_id}/report`, `GET /task/{task_id}/artifacts`, and
  `GET /task/{task_id}/audit` are not yet wired to mutate registry state.

## Next Recommended Phases

- Wire plan, QC, and run endpoints to registry status transitions.
- Define the input file validation contract before reading any real files.
- Define the output artifact directory contract before creating artifacts.
- Introduce an execution adapter interface with mock and dry-run backends first.
- Only later integrate real RNA-seq tools after state, validation, artifact,
  and execution adapter contracts are tested.
- Any production execution path must be designed separately with controlled
  runner, worker, and persistence boundaries.
