# Phase 7.3 Request Limits and Timeout Hardening

## Purpose and relationship to Phase 7.1 and 7.2

Phase 7.3 adds optional request-body protection and a timeout configuration scaffold to the Phase 7.1 security baseline and Phase 7.2 API-key scaffold. It does not change endpoint schemas. Request limiting is disabled by default, so existing clients retain their current behavior.

## Configuration

- `BIOINFO_MAX_REQUEST_BYTES`: unset, empty, zero, negative, or invalid values disable the global request-body guard. A positive integer enables it.
- `BIOINFO_REQUEST_TIMEOUT_SECONDS`: a positive numeric value records the intended end-to-end request timeout. It defaults to disabled and is not an application-level cancellation timer in this phase.
- `BIOINFO_MAX_METADATA_BYTES`: optional and disabled by default for a future metadata-specific input limit.
- `BIOINFO_MAX_COUNT_MATRIX_BYTES`: optional and disabled by default for a future count-matrix-specific input limit.

Invalid configuration is normalized deterministically without including the raw value in a response or log. The input-specific values do not yet add endpoint-specific enforcement.

## HTTP 413 behavior and middleware ordering

When enabled, the guard checks `Content-Length` when available and also counts actual streamed request bytes without making a second full body copy. An oversized body receives HTTP 413:

```json
{"detail":{"code":"REQUEST_BODY_TOO_LARGE","message":"Request body exceeds the configured limit."}}
```

API-key authentication is the outer middleware for protected `/task` routes. A missing or wrong key receives the existing sanitized 401 before body evaluation; a correctly authenticated oversized body receives 413. With authentication disabled, the size guard operates normally. Bodyless health and OpenAPI GET requests remain accessible.

Errors and logs contain no body content, no configured byte counts, no secrets, and no local paths. They contain no tracebacks or internal exception details.

## Timeout strategy

Application-level cancellation is intentionally not implemented because a generic request timer could interrupt persistent task-state writes. Operators should align the reverse proxy or API gateway timeout with the Coze tool timeout compatibility window. Uvicorn worker/process timeout and graceful-shutdown settings should allow state transitions to complete.

Timeout budgets should distinguish the minimal workflow timeout, controlled DESeq2 subprocess timeout, artifact download timeout and streaming behavior, and input registration considerations. Registration references trusted-root files rather than uploading arbitrary filesystem content. Long-running analysis should ultimately use an asynchronous task lifecycle.

## Known limitations and future Phase 7 candidates

- No rate limiting yet and no per-user quotas.
- No distributed timeout coordination.
- No endpoint-specific metadata or count-matrix enforcement yet.
- No public deployment and no real Coze publication.

Future candidates include identity-aware quotas, coordinated deadlines, safe subprocess cancellation, gateway profiles, and privacy-safe rejection metrics.
