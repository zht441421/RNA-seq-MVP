# Phase 5.1 Persistent Task Storage

Phase 5.1 introduces a local persistent task storage foundation for task
metadata, status, lifecycle events, and artifact metadata. It does not change
analysis behavior, public API paths, or the Phase 4 Bulk RNA-seq and DESeq2
execution contracts.

## Purpose

The goal is to preserve task lifecycle state across process restarts while
keeping the existing deterministic in-memory registry available for tests and
development workflows.

## SQLite Local Task Store

The storage layer uses SQLite from the Python standard library. No SQLAlchemy,
PostgreSQL, MySQL, database server, Docker, Snakemake, Nextflow, frontend code,
or Coze API integration is added in this phase.

The store is implemented in:

```text
backend/app/services/task_store.py
```

## Storage Path

The task store path is configured with:

```text
BIOINFO_TASK_STORE_PATH
```

If the variable is not set, the default is:

```text
data/state/tasks.sqlite3
```

The parent directory is created automatically. The database path is internal
and must not appear in public API responses.

## What Is Persisted

Phase 5.1 persists:

- task ID
- task status
- task creation and update timestamps
- task message and request metadata
- lifecycle/audit events
- artifact metadata with safe relative paths

Artifact metadata stores safe relative paths such as:

```text
tasks/task_0001/report.md
```

It does not store local absolute paths in public-facing artifact payloads.

## What Is Not Persisted

Phase 5.1 does not persist:

- uploaded files
- downloaded files
- raw analysis input file contents
- generated artifact file contents
- durable report bodies
- frontend state
- Coze API calls or responses
- production authentication or authorization state

The current task output files remain under the existing configured output root.

## Safety Boundaries

The persistent store keeps the Phase 4 safety boundaries:

- no local absolute paths in public responses
- sanitized errors
- no traceback exposure
- no tokens, passwords, or secrets exposure
- no fake p-values
- no automatic package installation
- no bioinformatics execution behavior changes
- task-scoped artifact paths only

## Current Limitations

- SQLite is a local development and release-candidate foundation, not a
  production multi-user database contract.
- The in-memory registry remains the first-level runtime cache.
- Artifact metadata is persisted, but file upload/download endpoints are not
  implemented yet.
- Existing task IDs remain deterministic (`task_0001`, `task_0002`, and so on).

## Future Migration Path

If Phase 5 later needs production database behavior, the SQLite-backed
`TaskStore` interface can be migrated or adapted to PostgreSQL or another
production database. A future migration should preserve public API response
shapes and keep storage paths, credentials, and internal errors out of public
responses.
