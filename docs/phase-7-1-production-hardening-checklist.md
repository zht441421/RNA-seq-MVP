# Phase 7.1 Production Hardening Checklist

Use this checklist before any public API or Coze exposure. Items are deployment
requirements, not claims about the current local-only backend.

## Access Control And Edge

- [ ] Put the service behind a TLS reverse proxy or API gateway.
- [ ] Require access control for every non-health operation; do not rely on an
  obscure base URL.
- [ ] Pass an API key in the approved header, never in a URL, and source it from
  deployment secrets management.
- [ ] Confirm key rotation, revocation, redaction, and least-privilege ownership.
- [ ] Restrict network ingress and administrative access.

## Browser And Request Controls

- [ ] Keep CORS default-deny; list only trusted browser origins if a frontend is
  later approved.
- [ ] Configure request size limits for bodies, metadata, count matrices, and
  input registration or future uploads.
- [ ] Configure connection, request, analysis, and download timeout limits.
- [ ] Add rate limiting and concurrency controls before untrusted exposure.

## Filesystem Roots And Artifact Downloads

- [ ] Configure dedicated, least-privilege input and output filesystem roots.
- [ ] Verify registration cannot escape input roots or perform arbitrary reads.
- [ ] Verify outputs remain inside output roots and public responses contain no
  absolute host paths.
- [ ] Allow artifact downloads only for task-scoped registered artifacts.
- [ ] Test traversal, unknown artifact, symlink, and cross-task rejection.
- [ ] Confirm responses provide relative download URLs only.

## Errors And Logging

- [ ] Verify error sanitization removes stack details, local paths, internal
  commands, credential material, and raw subprocess output.
- [ ] Confirm production logging redacts authentication headers and avoids raw
  user data, request bodies, metadata, count matrices, and artifact contents.
- [ ] Configure structured correlation identifiers, restricted log access,
  rotation, retention, and monitoring alerts.

## State, Analysis, And Operations

- [ ] Restrict SQLite file and directory permissions to the service identity.
- [ ] Schedule SQLite/state backups, test restoration, and define cleanup and
  retention procedures.
- [ ] Keep the DESeq2 subprocess behind preflight and allowlisted adapters; use
  fixed argument arrays, sanitized errors, and resource/time boundaries.
- [ ] Run unit tests and the local HTTP smoke tests in an isolated environment.
- [ ] Inspect smoke-test responses, artifact downloads, errors, and logs for
  public-safety regressions.

## Coze Exposure And Rollback

- [ ] Publish a Coze base URL only after TLS, gateway authentication, access
  restrictions, monitoring, and owner approval are active.
- [ ] Keep real Coze credentials out of repository files and validation output.
- [ ] Review the draft tool scope and do not expose unintended routes.
- [ ] Record verified rollback tags and the operator steps for restoring the
  prior application and compatible SQLite/state backup.
- [ ] Re-run health, contract, and smoke checks after deployment or rollback.

## Known Limitations And Future Hardening

- [ ] Acknowledge before approval that built-in auth, rate limiting, a frontend,
  real Coze publication, and public deployment are not part of Phase 7.1.
- [ ] Track future hardening items: optional API key middleware, request limits,
  application timeouts, structured security headers, explicit CORS settings,
  secrets management, authorization scopes, privacy controls, and incident
  response.
