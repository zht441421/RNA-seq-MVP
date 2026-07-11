# Phase 8.2 Coze Tool Interface / Agent Invocation Layer Preparation

## Scope and status

Phase 8.2 defines seven stable, machine-readable tools over the existing task
API. It does not deploy or publish a Coze plugin, add a public base URL, upload
files to Coze, or change RNA-seq/DESeq2 computation. The canonical definitions
are in `backend/app/contracts/coze_tools.py`; the portable manifest is
`docs/coze-tool-manifest.json`.

Run `python scripts/verify_phase_8_2_coze_tool_interface.py` to check required
files, manifest/OpenAPI bindings, and the full pytest suite. Use `--skip-tests`
only for a fast structural check.

## Agent calling flow

1. Call `create_analysis_task` and retain the returned `task_id`.
2. Register task inputs through the existing task-scoped input API when needed.
3. Call `validate_input`; stop and present sanitized validation errors when
   `valid` is false.
4. Complete the existing plan and QC preparation calls and obtain explicit user
   confirmation for method, contrast, and direction.
5. Call `start_analysis` with the confirmed configuration.
6. Poll `get_task_status` with bounded intervals and an overall timeout.
7. Call `get_analysis_summary`, then `list_artifacts`.
8. Call `download_artifact` only with an available name returned for the same
   task.

The tool layer does not bypass current lifecycle guards. A `409` means the
caller must query status and correct the call sequence.

## Tool lifecycle

`create_analysis_task` creates the durable task identity. Validation is
non-executing. `start_analysis` is allowed only after the current planning/QC
preconditions and explicit scientific choices are satisfied. Status and
summary calls are read projections; artifact listing may preserve the existing
placeholder lifecycle behavior. Download is task-scoped and does not accept a
filesystem path.

## Authentication expectations

All tool bindings target `/task` routes and therefore retain optional API-key
authentication, request-size limits, rate limiting, request correlation, and
audit/execution tracing. External exposure must enable API-key authentication,
use TLS, and keep credentials outside prompts, payloads, URLs, logs, and
manifests. The default header is `X-Bioinfo-API-Key`; tools never accept a key
as a parameter.

## Polling model

Poll `get_task_status` at bounded intervals, avoid concurrent duplicate starts,
and enforce a caller-side deadline. Honor `Retry-After` for `429`; use only
conservative bounded retries for `503`. Do not retry `400`, `401`, `404`, `409`,
`413`, or `422` blindly. An HTTP success is not evidence that a formal method
ran: method flags, status, warnings, limitations, reliability information, and
artifacts are authoritative.

## Summary and scientific safety

The summary includes task status, safe artifact references, sanitized messages,
and reliability information when available. `reliability_information.available`
is false when no grade is present; absence must never be treated as high
reliability. The AI layer may summarize supported fields but must not invent
methods, significance, causal claims, enrichment, or biological conclusions.
It must preserve interpretation boundaries and distinguish exploratory
CPM/log2FC output from formal DESeq2 results.

## Artifact retrieval flow

First call `list_artifacts` or use `artifact_references` from the summary. Select
only an entry marked available and pass its exact task ID and artifact name to
`download_artifact`. Never construct or expose a local path. Existing checks
reject traversal, absolute paths, missing files, and cross-task access with
sanitized errors.

## Failure handling

Errors use HTTP status plus a sanitized JSON body, and responses carry
`X-Request-ID` for support correlation. Do not reveal stack traces, internal
commands, storage roots, credentials, or configuration. Present validation and
scientific limitations to the user; for unexpected operational failures,
present a neutral message and the request ID only.

## Current limitations and future Coze path

There is no real Coze deployment, plugin publication, hosted upload flow,
public base URL, OAuth flow, or production gateway. A future phase can deploy a
trusted API, enable authentication and gateway controls, import the reviewed
manifest/OpenAPI operations, configure secrets in the platform, and perform
end-to-end invocation tests before publication.
