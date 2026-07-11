# Phase 7.6 Audit and Execution Trace Hardening Scaffold

## Audit goals

Phase 7.6 strengthens internal traceability without changing RNA-seq calculations, DESeq2 execution, public API models, routes, or scientific artifacts. It links operational requests to task execution records and existing lifecycle events.

## Trace metadata

Task creation and execution receive an opaque `trace_id`. Internal records include `request_id`, `task_id`, operation, UTC start/end timestamps, monotonic duration, and status. Failed executions store only an allowlisted sanitized reason. Raw exceptions, paths, commands, credentials, environment dumps, and tracebacks are excluded.

The trace registry is process-local. Existing `X-Request-ID` behavior provides request linkage; no new public response schema is added.

## Lifecycle events

Existing successful event names, metadata, and state transitions remain unchanged: task creation, planning/validation or QC, execution, reporting, and artifact listing remain auditable. The internal trace registry links these operations by task ID without changing successful public audit responses. Failures add `analysis_failed`, or enrich an existing validation-failure event, with sanitized trace metadata.

## Reproducibility purpose

Traces include analysis and runner versions, a SHA-256 identifier of an allowlisted configuration snapshot, and a minimal runtime placeholder. The identifier is a hash, not a configuration dump. This complements existing execution timestamps, durations, manifests, and audits without changing scientific contents.

## Current limitations and future migration

Traces reset on restart, are not shared between workers, and are not a durable provenance ledger or distributed trace. A later phase can persist the same safe metadata in an append-only audit store, add retention/access policies, and link artifact checksums. No external database, Kafka, workflow engine, or tracing infrastructure is introduced.
