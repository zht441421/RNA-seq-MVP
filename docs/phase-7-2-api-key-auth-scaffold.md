# Phase 7.2 Optional API Key Auth Scaffold

## Purpose And Relationship To Phase 7.1

Phase 7.2 implements the optional API key control proposed by the Phase 7.1
production-facing security baseline. It provides a small authentication
boundary for future external API or Coze use without claiming production
readiness or changing the default local workflow.

## Disabled By Default

Authentication is disabled by default. With the environment variables unset,
all existing task endpoints keep their current behavior and response shapes.
Authentication is enabled only when `BIOINFO_REQUIRE_API_KEY` is set to an
accepted true value.

## Environment Variables

- `BIOINFO_REQUIRE_API_KEY`: defaults to false. Accepted true values are `1`,
  `true`, `yes`, and `on`; accepted false values are `0`, `false`, `no`, `off`,
  empty, or unset. Matching is case-insensitive and ignores surrounding space.
- `BIOINFO_API_KEY`: supplies the expected key and is required only when
  authentication is enabled.
- `BIOINFO_API_KEY_HEADER`: optional header-name override for reverse proxy/API
  gateway compatibility. It defaults to `X-Bioinfo-API-Key`.

The implementation uses constant-time comparison for a provided key. No
secrets belong in repository files, command output, URLs, responses, or logs.

## Protected Endpoint Policy

When authentication is enabled, every route under `/task` is protected. This
includes task creation, validation, plan, QC, run, input registration, formal
DE preflight, status, report, artifacts and artifact downloads, audit, and
Coze summary operations. Protecting the prefix also covers future task routes
unless they are deliberately reviewed and exempted.

## Public Health And OpenAPI Policy

`GET /health` remains public so a load balancer or local operator can perform a
minimal liveness check without receiving a credential. `GET /openapi.json`
also remains public to preserve the existing OpenAPI policy and schema tooling.
Neither endpoint returns protected task data. Deployment owners may restrict
schema access at a reverse proxy or API gateway if their policy requires it.

## Local Placeholder Example

Use a deployment-managed placeholder value during local verification; replace
it through an appropriate secret store rather than committing a value:

```powershell
$env:BIOINFO_REQUIRE_API_KEY = "true"
$env:BIOINFO_API_KEY = "replace-with-local-placeholder"
$env:BIOINFO_API_KEY_HEADER = "X-Bioinfo-API-Key"
uvicorn backend.app.main:app
```

Send the configured header on task requests. Clear these environment variables
to restore the default disabled behavior. Do not put the key in a URL.

## Coze And Gateway Configuration Notes

For future Coze integration, configure `X-Bioinfo-API-Key` at the gateway/tool
layer as a secret header, not as a URL parameter or prompt-visible value. If a
gateway requires another header, configure the same reviewed name in
`BIOINFO_API_KEY_HEADER`. Prefer TLS termination, authentication, request
limits, and redaction at a reverse proxy/API gateway even when backend checking
is enabled.

## Sanitized Error Behavior

A missing or incorrect request key produces the same sanitized 401 response.
If authentication is required but the expected key is unavailable, or the
boolean setting is invalid, a protected endpoint fails safely with a sanitized
503. Errors reveal no expected or provided key, environment value, local path,
stack detail, or internal configuration. There must be no secrets in responses/logs.

## Testing

Run the focused tests and offline baseline helper:

```powershell
python -m pytest tests\test_phase_7_2_api_key_auth_settings.py tests\test_phase_7_2_api_key_auth_behavior.py tests\test_phase_7_2_api_key_auth_docs.py tests\test_phase_7_2_api_key_auth_baseline_script.py
python scripts\print_phase_7_2_api_key_auth_baseline.py
```

The tests exercise disabled, accepted boolean, correct-key, missing-key,
wrong-key, missing-configuration, public health, and public OpenAPI behavior.
They use local `TestClient` requests and make no network calls.

## Known Limitations

- There is no rate limiting yet.
- There is no user-level auth or per-task authorization.
- There is no OAuth or identity-provider integration.
- There is no public deployment.
- There is no real Coze publication.
- A shared API key is a coarse service boundary, not a complete production
  identity and authorization system.

## Future Phase 7 Candidates

- Rate limiting and concurrency controls.
- Request size limits and execution timeouts.
- Structured security headers.
- Explicit CORS config.
- Production secrets management, rotation, and revocation.
- User-level identity, authorization scopes, monitoring, and audit policy.
