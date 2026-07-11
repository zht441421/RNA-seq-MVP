# Phase 8.1 Coze Integration Contract Preparation

## Purpose and status

Phase 8.1 prepares a stable backend contract for a future Coze agent or plugin.
It does not publish a plugin, deploy the API, create a frontend, or call Coze.
The machine-readable draft manifest is
`backend/app/contracts/coze_integration_manifest.json`.

## Future interaction model

A future trusted Coze adapter may orchestrate the existing task API:

1. Create a task with `POST /task/create` and retain `task_id`.
2. Register metadata and count-matrix inputs separately with
   `POST /task/{task_id}/inputs/register`, using safe relative paths only.
3. Validate inputs with `POST /task/validate-inputs`.
4. Use the existing `POST /task/plan` and `POST /task/qc` preparation calls to
   advance the current task lifecycle before execution.
5. Run the explicitly selected workflow with `POST /task/run`.
6. Poll `GET /task/{task_id}/status`.
7. Retrieve `GET /task/{task_id}/coze-summary` for concise result presentation.
8. List `GET /task/{task_id}/artifacts`, then download only a returned artifact
   through `GET /task/{task_id}/artifacts/{artifact_name}/download`.

The adapter must preserve explicit user confirmation and contrast direction.
It must not infer that DESeq2 ran, invent statistical significance, or turn an
exploratory summary into a scientific conclusion.

## Available backend capabilities

The contract covers task creation, task-scoped input registration, input
validation, analysis execution, lifecycle status, safe result summaries,
artifact listings, and task-scoped downloads. The existing summary layer
provides a concise status, warnings, limitations, result-file representation,
relative download links, and a `safe_to_present` signal. It does not generate
new analysis or conclusions.

## Authentication and security expectations

Task routes use the existing optional API-key middleware. It remains disabled
by default for local compatibility, but an external deployment must enable it,
provision the key outside this repository, use TLS, and keep the configured
header private. The default header name is `X-Bioinfo-API-Key`.

Request-size limits, rate limiting, request correlation, sanitized errors, and
execution tracing remain in force. Every HTTP response includes
`X-Request-ID`. The adapter must never place credentials in prompts, logs,
payload fields, URLs, or manifest files.

## Task lifecycle contract

The current lifecycle progresses through creation, planning, QC preparation,
execution, reporting, and artifact review. A `409` indicates an invalid state
transition; the adapter should query status and correct its call sequence rather
than retrying blindly. A completed HTTP request is not proof that a formal
scientific method ran: the response status, method fields, warnings,
limitations, and artifacts remain authoritative.

## Artifact retrieval contract

Artifact list and summary responses use task-scoped relative API references.
The adapter must use an artifact name returned for the same task and must not
construct a filesystem path. Unknown, missing, cross-task, traversal, or
absolute-path requests are rejected with sanitized `400` or `404` responses.
No local storage root is part of this contract.

## Status, result, and artifact projections

- Status: `task_id`, lifecycle `status`, and concise `message`.
- Result summary: method flags, safe summary text, warnings, limitations,
  contrast direction when available, result files, and relative download links.
- Artifact list: task ID, lifecycle status, artifact name/type/availability,
  safe relative reference, and limitations.

These are projections of existing responses; Phase 8.1 adds no response fields.

## Error handling contract

Errors use an HTTP status and sanitized JSON `detail`, while rate limiting keeps
its existing structured `error` envelope. `X-Request-ID` is the correlation
value for operational support. A future adapter may retry `429` according to
`Retry-After` and may retry `503` conservatively. It should not automatically
retry validation, authentication, state-transition, payload-size, or not-found
errors (`400`, `401`, `404`, `409`, `413`, `422`). Public responses must never
include tracebacks, local paths, commands, credentials, or configuration dumps.

## Current limitations and future path

This is contract preparation only. There is no public base URL, Coze tool
registration, publication, OAuth flow, frontend, hosted file upload, or
production gateway. A future phase may select a trusted deployment base URL,
enable authentication and gateway controls, import the reviewed OpenAPI subset,
map manifest operations to Coze tools, and run end-to-end contract tests before
publication.
