# Phase 7.4 Optional Rate Limiting Scaffold

## Purpose

Phase 7.4 adds lightweight abuse protection for deployments that choose to
enable it. The limiter is disabled by default, so local development, existing
routes, and existing clients require no configuration changes.

## Configuration

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `RATE_LIMIT_ENABLED` | `false` | Enables the in-process limiter. |
| `RATE_LIMIT_REQUESTS` | `60` | Requests allowed per client in one window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Fixed-window duration in seconds. |
| `RATE_LIMIT_SCOPE` | `ip` | Client identity strategy; only `ip` is supported. |
| `RATE_LIMIT_EXEMPT_PATHS` | `/health,/docs,/openapi.json` | Comma-separated exact paths that bypass limiting. |

When enabled, the middleware identifies a client from the ASGI client IP. An
over-limit request receives HTTP 429, a `Retry-After` header, and a sanitized
`rate_limit_exceeded` JSON error. API-key authentication remains the outer
security check, and the request-body limit remains active after rate limiting.

## Default behavior

With `RATE_LIMIT_ENABLED` unset or false, requests pass through unchanged.
Health, documentation, and OpenAPI paths are exempt by default even when the
limiter is enabled.

## Limitations

Counters live only in application memory. They reset on restart, are not shared
between processes or replicas, and provide no durable or globally coordinated
quota. IP identity can group clients behind a proxy or NAT; trusted proxy
configuration is an infrastructure responsibility. This scaffold is not a
substitute for production gateway-level throttling and adds no Redis or other
external dependency.

## Future migration

The limiter is isolated as an ASGI middleware. A later phase can preserve the
configuration and error contract while replacing its in-memory counter store
with Redis, or can move enforcement to a trusted API gateway. Multi-instance
production deployments should prefer gateway or shared-store enforcement.
