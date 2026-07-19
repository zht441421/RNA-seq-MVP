# Phase 8.5 Protected Local Staging Deployment

## Scope and outcome

Phase 8.5 packages the existing FastAPI backend as a protected, single-host,
local staging service. It validates the future deployment boundary without
changing an API schema, RNA-seq logic, DESeq2 behavior, or any Coze contract.
There is **no remote deployment**, Coze publication, production endpoint,
public exposure, cloud service, or private biological dataset in this phase.

The staging stack is intentionally small:

```text
local caller -> 127.0.0.1:8443 (TLS nginx) -> internal network -> API:8000
                                                        |-> SQLite state volume
                                                        |-> artifact volume
                                                        |-> read-only demo inputs
```

The host publishes only loopback ports. The API has no published host port and
does not trust proxy headers. Nginx replaces forwarding headers with values
from the local proxy boundary. Both containers drop Linux capabilities, enable
`no-new-privileges`, and use read-only root filesystems. The API runs as UID
10001 with one worker, which matches the current in-memory rate limit and trace
implementation.

## Prepare and start

Requirements are Docker with Compose, Python, and OpenSSL. These commands are
local operations; they do not log in to a registry or deploy remotely.

```powershell
python scripts/prepare_phase_8_5_local_staging.py
docker compose -f docker-compose.staging.yml config --quiet
docker compose -f docker-compose.staging.yml up --build -d
docker compose -f docker-compose.staging.yml ps
```

The preparation command generates a random API key and a two-day self-signed
certificate under `.staging-secrets/`. That directory is ignored by Git. No
secret value is printed, included in the image, stored in Compose, or committed.
The self-signed certificate is suitable only for this loopback test.

Use `https://127.0.0.1:8443` for local staging. Plain HTTP on port 8080 returns
a redirect to the local HTTPS endpoint. Clients must send the API key in
`X-Bioinfo-API-Key` on protected routes. The public `/health` endpoint proves
only that the process can answer; a successful protected workflow smoke test is
the functional readiness check and DESeq2 preflight is a separate capability
check.

## Secret rotation and environment separation

Rotate local material with:

```powershell
python scripts/prepare_phase_8_5_local_staging.py --rotate
docker compose -f docker-compose.staging.yml up -d --force-recreate
```

Secret rotation invalidates the old API key. Staging and production credentials
must always be different. A future non-local environment must use its own secret
manager and a trusted CA certificate; copying `.staging-secrets/` is forbidden.
The Compose file enforces authentication, request-size limits, request timeout,
rate limiting, internal storage roots, and local environment/build labels.
Firewall policy, certificate issuance, host patching, backups, and centralized
log retention remain operator controls and are not claimed by this local stack.

## Verification and smoke test

Run the offline structure, Phase 8.4 Golden Result, and full regression gate:

```powershell
python scripts/verify_phase_8_5_protected_staging.py
```

With the stack running, exercise authentication, request IDs, the complete
minimal workflow, task polling, safe summary, artifacts, downloads, audit,
path-traversal rejection, cross-task artifact rejection, DESeq2 preflight, and
the Phase 8.4 Golden Result through HTTPS:

```powershell
python scripts/smoke_phase_8_5_protected_staging.py
docker compose -f docker-compose.staging.yml restart api
python scripts/smoke_phase_8_5_protected_staging.py
```

The second smoke run checks persistence after restart. The synthetic fixture
validates workflow behavior and safety boundaries; it does not prove scientific validity.
The exploratory minimal workflow must not produce
p-values, adjusted p-values, or unsupported scientific conclusions. DESeq2
readiness is reported from the real preflight response and is never simulated.

## Persistence, restart, and observability

SQLite task records, registered input metadata, lifecycle audit events, artifact
metadata, and artifact files persist in named volumes. An incomplete task keeps
its last persisted state after restart; there is no automatic resume or recovery
engine. If the process stops during a synchronous request, inspect its persisted
status and audit before retrying—do not assume completion.

Execution trace entries and rate limit counters are process-local and reset on
restart. This limitation is explicit: Phase 8.5 preserves audit tracing during
normal execution but does not add Redis, a workflow engine, or distributed
tracing. Structured logs include request IDs and safe route information; the
proxy access log excludes request headers, API keys, response bodies, and local
filesystem paths.

Useful local diagnostics:

```powershell
docker compose -f docker-compose.staging.yml ps
docker compose -f docker-compose.staging.yml logs --no-log-prefix api proxy
```

Do not paste logs into public systems without review. Responses and logs must
not expose secrets, internal stack traces, or host paths.

## Rollback and cleanup

Rollback is an operator-controlled local procedure:

1. **Automated and locally tested:** run the smoke test before a change and save
   the reported completed/incomplete task identifiers.
2. **Manual staging operation:** stop the stack with
   `docker compose -f docker-compose.staging.yml down`. Named volumes remain.
3. **Manual staging operation:** restore the previously verified image/build ID
   and start Compose again, then rerun the smoke test and persistence check.
4. **Not tested in Phase 8.5:** restoration from an external volume backup.
   Establish and rehearse that procedure before any real staging data is used.

Data retention is manual. `down` is non-destructive to named volumes. Only after
confirming retention requirements and backup status may an operator deliberately
run `docker compose -f docker-compose.staging.yml down -v`. Removing volumes or
`.staging-secrets/` permanently removes local state or credentials and is not
performed by verification scripts.

## Security and release checklist

- Keep host binding on `127.0.0.1`; do not expose these local ports publicly.
- Keep API authentication, request limits, rate limit, request IDs, audit, and
  task-scoped artifact checks enabled.
- Never commit `.staging-secrets/`, `.staging-runtime/`, SQLite files, artifacts,
  private keys, real patient data, tokens, passwords, or external base URLs.
- Confirm the seven Phase 8.2 tool operation IDs and Phase 8.4 Golden Result gate.
- Record the exact commit/build ID used for a staging run.
- Treat `/health`, functional readiness, and DESeq2 capability as separate facts.

Phase 8.6 is the next gate: reference dataset validation against this protected
boundary. Real Coze end-to-end integration remains Phase 8.7. Neither step may
reinterpret exploratory output as formal scientific evidence.
