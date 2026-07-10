# Phase 7.1 API Security Baseline

## Purpose

Phase 7.1 establishes a production-facing hardening / API security baseline for
eventual external API or Coze exposure. It records controls that a deployment
owner must apply before exposure; it does not claim that the current backend is
production-ready.

## Relationship To The Phase 6 Deployment-Readiness Baseline

The Phase 6 deployment-readiness baseline documented local launch, the draft
Coze contract, smoke verification, and operator procedures. Phase 7.1 builds on
that operational baseline with a threat model and security boundaries. It does
not change runtime routes, schemas, response shapes, or analysis behavior.

## Threat Model And Current Assumption

The backend is currently assumed to be non-public and local-only. Future
external exposure could introduce unauthenticated callers, credential theft,
oversized or malformed requests, denial-of-service traffic, malicious input
registration, path traversal, artifact enumeration, sensitive error output,
and misuse of analysis subprocesses. A future Coze/API integration also creates
risks around a publicly reachable base URL, gateway credentials, request logs,
and overly broad plugin access.

## Access Control Strategy

- Require an API key or gateway-level authentication before external exposure;
  do not rely on obscurity or an unlisted URL.
- Use `X-Bioinfo-API-Key` as the recommended API key header name if a shared-key
  scheme is selected. Do not put secrets in URLs or query strings.
- Authenticate first at a TLS-terminating reverse proxy or API gateway. Optional
  backend-level API key support may be added later as defense in depth.
- Store keys in deployment secrets management, rotate them, scope access where
  the gateway permits it, and never return or log key values.

No built-in authentication is enforced by this baseline.

## CORS Policy Guidance

Use a default-deny CORS policy for browser clients. If a frontend is added,
allow only explicit trusted origins, methods, and headers; do not combine
wildcard origins with credentials. Server-to-server Coze traffic does not need
broad browser CORS access.

## Request Size And Timeout Limits

Enforce request size limits at the reverse proxy or API gateway before public
exposure, with backend validation added where useful. Set documented limits for
metadata and count matrix size, input registration or future upload size, field
counts, and total body bytes. Apply connection, request, analysis, and artifact
download timeout limits. Reject excessive input before expensive parsing or
execution, while keeping limits compatible with approved datasets.

## Filesystem Safety

- Constrain registration to configured input roots and generated artifacts to
  configured output roots.
- Permit no arbitrary filesystem reads and resolve paths before containment
  checks, including symlink-aware deployment controls.
- Provide no local absolute paths in public API responses.
- Return relative download URLs only; deployment infrastructure may convert
  them to an approved external origin.
- Keep deployment state, inputs, and outputs outside web-server static roots.

## Error Response Safety

Public errors must be sanitized and stable. The public contract is **no
traceback/token/password/secret leakage**: responses must contain no stack
details, credentials, internal commands, subprocess command lines, or local
paths. Record a correlation identifier rather than exposing diagnostic detail;
keep restricted operator diagnostics separately.

## Artifact Download Safety

Artifact download safety requires task-scoped, registered artifacts only.
Resolve the requested artifact from stored task metadata, verify containment in
the configured output root, reject path traversal and unregistered names, and
apply authorization before download when authentication is introduced. Do not
turn a caller-supplied path into a filesystem response.

## SQLite And State Safety

Restrict local SQLite state file and parent-directory permissions to the service
identity. Protect backups with equivalent access controls, test restoration,
and define retention, cleanup, and secure disposal procedures. Stop or use a
SQLite-safe backup method before copying live state. Do not expose the state
file as a downloadable artifact.

## Logging Safety

Production logging must contain no secrets. Redact authentication headers and
avoid raw user data, metadata rows, count matrices, artifact contents, request
bodies, and local paths. Prefer structured events with task identifiers,
outcomes, durations, and correlation identifiers. Restrict access, rotation,
retention, and export destinations.

## DESeq2 Subprocess Safety

Keep the DESeq2 subprocess behind the existing preflight boundaries and an
allowlisted execution adapter. Never use `shell=True` for user-controlled
values. Pass fixed executable arguments separately, validate method and
contrast fields, constrain working/input/output paths, set resource and timeout
limits, and sanitize R and subprocess errors before they reach a public
response. The same boundary must apply to future analysis executors.

## Recommended Production Checklist

Before exposure, complete the companion hardening checklist, deploy behind TLS
and an authenticating reverse proxy/API gateway, configure network allowlists,
set request and timeout limits, verify filesystem permissions, back up state,
run deterministic smoke tests, inspect public errors and logs, and document a
rollback using reviewed release tags. Add monitoring and incident ownership.

## Known Limitations

- No built-in auth is enforced yet.
- No rate limiting is implemented yet.
- No frontend is included.
- No real Coze publication has occurred.
- No public deployment is provided or validated.
- Application-level request size, CORS, and security-header enforcement are not
  added by this documentation-only phase.

## Future Phase 7 Candidates

- Optional API key middleware, disabled by default until explicitly configured.
- Request size limits and analysis-aware timeout enforcement.
- Gateway and application rate limiting with deterministic rejection behavior.
- Structured security headers and explicit CORS configuration.
- Deployment secrets management, rotation, audit, and revocation procedures.
- Authorization scopes, monitoring, privacy/retention controls, and incident
  response exercises.
