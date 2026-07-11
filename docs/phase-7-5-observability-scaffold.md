# Phase 7.5 Deployment Observability Scaffold

## Purpose

Phase 7.5 adds lightweight request correlation and structured operational
logging for future deployment diagnostics. It does not change bioinformatics,
RNA-seq, or DESeq2 behavior and requires no external service.

## Logging behavior

The application uses Python standard logging with a compact JSON formatter.
Request completion records contain a UTC timestamp, level, service name,
request ID, route template, HTTP method, status code, and duration in
milliseconds. A task ID is included when FastAPI resolved one from the route.
Unexpected application errors are logged as `request_failed` without returning
exception or traceback details to the caller.

Logs are written to the process logging stream. Operators remain responsible
for collection, retention, access controls, redaction policy, and alerting.

## Request IDs

An outermost ASGI middleware generates a new opaque request ID for every HTTP
request. The value is returned in `X-Request-ID` and included in the associated
request log. The server generates the value rather than trusting a caller's
header. Authentication failures, rate-limit responses, request-size failures,
normal route responses, and sanitized unexpected errors are all correlated.

## Health endpoint

`GET /health` remains public and retains its existing `status`, `service`, and
`phase` fields. It now also reports the non-sensitive application `version`.
It does not expose paths, environment variables, credentials, commands, or
dependency internals.

## Audit metadata

Existing task audit events retain their timestamp metadata, and existing
execution results retain their duration metadata. Request IDs, route timing,
and status codes are recorded in the operational request log rather than added
to public audit response schemas or scientific artifact formats. The existing
audit architecture is otherwise unchanged.

## Current limitations and future migration

This scaffold has no metrics server, persistent log store, distributed trace,
cross-service propagation, or alerting. Request IDs correlate one application
request only. A future deployment can ship the JSON logs to a managed log
collector, add metrics at an API gateway, and propagate correlation through
trusted services. OpenTelemetry or another tracing system may be evaluated in
a later phase; none is introduced here.
