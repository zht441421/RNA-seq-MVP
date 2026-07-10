# Phase 6.4 Deployment Runbook And Operator Checklist

Phase 6.4 turns the existing deployment contract and local launch validation
into an operator-facing runbook. It adds documentation and deterministic
documentation-validation tests only. It does not change runtime behavior,
analysis behavior, routes, schemas, public API response shapes, or the task
lifecycle.

## Purpose

This runbook explains how an operator can prepare directories and environment
variables, launch the existing FastAPI application, verify it locally,
troubleshoot common failures, and decide whether it is safe to place behind a
protected API gateway or reverse proxy.

No public deployment is required by this phase, and no real Coze API call is
made. Following this runbook prepares a deployment; it does not by itself make
the backend production-ready or publish a Coze plugin.

## Relationship To Phases 6.1, 6.2, And 6.3

- Phase 6.1 defines the application entrypoint, deployment environment
  variables, API sequence, response shapes, and public-response safety
  boundaries.
- Phase 6.2 provides draft Coze plugin metadata, an OpenAPI endpoint subset,
  field mappings, and an offline manifest validator. Those files remain draft
  preparation artifacts, not a published plugin.
- Phase 6.3 launches Uvicorn on loopback and validates the existing task
  lifecycle through real local HTTP requests with isolated input, output, and
  SQLite state.
- Phase 6.4 assembles those materials into repeatable launch, verification,
  exposure, troubleshooting, shutdown, and rollback procedures.

The earlier contracts remain authoritative. This runbook does not replace or
silently revise them.

## Deployment Boundary

The supported Phase 6.4 deployment unit is the existing FastAPI application:

```text
backend.app.main:app
```

The deterministic deployment-validation workflow is
`minimal_cpm_log2fc`. It needs Python and the packages in `requirements.txt`;
it does not require R, Docker, or a database server. DESeq2 is optional and
remains gated by `GET /task/formal-de/preflight`. An operator must not claim
DESeq2 readiness unless that response reports ready and the actual run
completes.

This backend currently has no production authentication or authorization
layer, no public upload endpoint, no production task queue, and no multi-node
coordination. A reverse proxy or API gateway and its security controls are
deployment prerequisites for any external exposure.

## Prerequisites

Run every command from the repository root. Before launch, record the exact
source revision and deployment configuration so the same version can be
restored during rollback.

The operator needs:

- a supported Python environment with `python`, `pip`, and `uvicorn`
  available
- dependencies installed from the checked-in `requirements.txt`
- read access to the configured input root
- write access to the output root and the parent directory of the SQLite task
  store
- an available TCP port
- trusted, pre-staged metadata and count-matrix files for any real task
- a reverse proxy or API gateway if the service will be reachable outside the
  host

Install the checked-in Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

The minimal workflow has no Docker runtime requirement. Do not introduce
Docker, Snakemake, Nextflow, another workflow engine, or a database server as a
Phase 6.4 launch prerequisite.

## Environment And Directory Preparation

The backend uses these deployment-local settings:

| Setting | Default | Operator requirement |
| --- | --- | --- |
| `BIOINFO_INPUT_ROOT` | `data/inputs` | Readable root containing only trusted, pre-staged inputs. |
| `BIOINFO_OUTPUT_ROOT` | `data/outputs` | Writable root for task-scoped artifacts. |
| `BIOINFO_TASK_STORE_PATH` | `data/state/tasks.sqlite3` | Writable local SQLite file whose parent directory persists across restarts. |

Create the default directory layout if it does not already exist:

```powershell
New-Item -ItemType Directory -Force data\inputs, data\outputs, data\state
```

For an operator-managed launch, set all three variables explicitly. This
PowerShell example keeps the default repository-local layout while resolving
it for the process:

```powershell
$env:BIOINFO_INPUT_ROOT = (Resolve-Path "data\inputs").Path
$env:BIOINFO_OUTPUT_ROOT = (Resolve-Path "data\outputs").Path
$env:BIOINFO_TASK_STORE_PATH = Join-Path (Resolve-Path "data\state").Path "tasks.sqlite3"
```

Deployment configuration may contain local absolute paths internally. Those
values belong only in the process environment and operator records; local
absolute paths must never appear in public API responses or Coze-facing
payloads.

Before launch:

1. Confirm the input root is not broadly writable by untrusted clients.
2. Confirm the output root and state directory are writable by the service
   account and are not served as static directories.
3. Keep inputs, outputs, and state separate from application source.
4. Give staging and production separate roots; do not share one SQLite file
   between environments.
5. Ensure the volume has enough free space for generated artifacts and state.
6. Define retention, backup, and cleanup ownership before accepting real data.

Clients register only safe relative paths beneath `BIOINFO_INPUT_ROOT`.
Staging a file is a trusted operator or storage-integration action; the current
public API does not upload files and must not be treated as an arbitrary
filesystem reader.

### File Upload And Input Registration Operations

There is no general file upload endpoint in the Phase 6 task contract. A
trusted operator or separately reviewed storage integration must place
metadata and count-matrix files beneath `BIOINFO_INPUT_ROOT` before a client
calls `POST /task/{task_id}/inputs/register`.

The registration request uses `source_relative_path`. It must not contain an
absolute path or path traversal. Keep unrelated files and credential material
outside the input root, grant the application read access only where practical,
and do not mount the input root as a public static directory.

### Artifact Storage Operations

Generated artifacts belong under `BIOINFO_OUTPUT_ROOT/tasks/{task_id}/`. The
API lists task-scoped artifact metadata and returns relative artifact download
URLs; it does not authorize direct browsing of the output root.

Monitor free space, preserve the relationship between a task record and its
artifact directory, and apply a documented retention policy. Perform cleanup
only after the retention owner confirms that the task and its artifacts may be
removed. A proxy must forward the reviewed artifact download endpoint rather
than serving `BIOINFO_OUTPUT_ROOT` directly.

### SQLite State Operations

`BIOINFO_TASK_STORE_PATH` is a local SQLite file, not a database server
connection. Keep it on persistent storage, keep its parent directory writable
by the service account, and use `--workers 1`. Record the configured state path
so a restart does not accidentally open an empty store at another location.

For backup or restore, stop or drain writes and treat the SQLite file and
`BIOINFO_OUTPUT_ROOT` as one consistent state set. Do not delete or replace
either location merely to recover from a health-check failure.

## Minimal Workflow And DESeq2 Readiness

The minimal workflow is ready when:

- Python dependencies from `requirements.txt` are installed
- both approved input files can be read beneath `BIOINFO_INPUT_ROOT`
- the output root and SQLite state location are writable
- the Phase 6.3 smoke test passes

`minimal_cpm_log2fc` does not require R, Rscript, BiocManager, DESeq2, or
Docker. Its CPM/log2FC result is exploratory and does not contain p-values or
adjusted p-values.

DESeq2 is an optional deployment capability. Before enabling it, the operator
must provide and validate:

- R
- Rscript
- BiocManager
- DESeq2

Then call `GET /task/formal-de/preflight`. A not-ready response is a normal,
safe gate: do not submit a DESeq2 run and do not claim that DESeq2 is available.
This runbook does not install or modify the R environment.

## Launch Commands And Bind Behavior

### Local Development

Use loopback and auto-reload for local development only:

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

`127.0.0.1` keeps the development server reachable only from the local host.

### Recommended Operator Command

For a stable local service or a same-host reverse-proxy upstream, omit reload
and use one worker:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

One worker is the supported conservative setting for the current local SQLite
task store and process-local lifecycle state. Do not enable multiple Uvicorn
workers until cross-process task creation, lifecycle consistency, SQLite
locking, and artifact writes have been deliberately validated.

### Public Or Reverse-Proxy Deployment

If a reverse proxy is on the same host, prefer `127.0.0.1`. If a platform or a
reverse proxy on a private network must reach Uvicorn, bind to `0.0.0.0` only
inside that restricted network:

```powershell
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

`0.0.0.0` is a listen address, not a security control.
Never expose the Uvicorn port directly to the public internet.
Firewall or security-group rules must
restrict the upstream port to the trusted proxy or platform. Do not use
`--reload` outside local development.

A process supervisor may start and restart this command, but no specific
container runtime or service manager is required by Phase 6.4.

## Reverse Proxy And Public Exposure

Before any external traffic reaches the application, configure the reverse
proxy or API gateway to provide:

- HTTPS and TLS termination
- authentication and authorization
- an explicit allow-list of intended methods and endpoint paths
- request-size limits and rate limits
- connection, request, and upstream timeouts
- restricted and explicitly trusted forwarded-header handling
- access-log redaction for credentials, sensitive query values, and private
  data
- denial of direct access to the Uvicorn port
- denial of static access to input, output, state, repository, and log
  directories
- a deliberate decision about whether interactive docs or the full OpenAPI
  document are externally reachable

CORS is not authentication. A successful `GET /health` is also not evidence
that authentication, storage permissions, the full task workflow, or DESeq2
are ready. Coze server-to-server requests do not require browser CORS by
default. If a separately approved browser client later requires CORS, review
its exact origins and methods in a later runtime phase; Phase 6.4 does not
implement or change CORS behavior.

Expose only reviewed API paths. Artifact links returned by the backend must
remain relative API paths such as:

```text
/task/task_0001/artifacts/report.md/download
```

The trusted proxy or client may join that relative path with an approved HTTPS
base URL. The backend response must not contain `file://` URLs or input,
output, state, repository, or operating-system absolute paths.

## Coze Base URL Preparation Notes

The Coze base URL is a deployment or plugin setting outside this backend. When
a future protected deployment is approved:

1. Choose one stable HTTPS origin owned by the deployment operator.
2. Terminate TLS and enforce access policy at the reverse proxy or API gateway.
3. Route the reviewed API paths to the private Uvicorn upstream.
4. Verify `GET /health` through the base URL from an authorized client.
5. Configure the draft Coze/OpenAPI material with that HTTPS origin only during
   a separately reviewed publication step.
6. Keep relative `/task/...` download URLs unchanged in backend responses.

Do not configure Coze with a local filesystem location, a loopback-only address
that Coze cannot reach, or a directly public Uvicorn port. Phase 6.4 neither
publishes the draft plugin nor calls the future base URL.

## Pre-Exposure Validation

Complete the offline and loopback checks before opening network traffic.

### 1. Run The Test Suite

```powershell
python -m pytest -q
```

A failure is a release blocker. Do not work around a contract or safety test at
the proxy layer.

### 2. Validate The Phase 6.2 Manifest Materials

```powershell
python scripts/validate_phase_6_2_coze_manifest.py
```

Expected success output:

```text
Phase 6.2 Coze manifest materials verified
```

Validation is offline and does not call Coze. Do not regenerate or edit the
OpenAPI subset during deployment unless an API-contract change has been
separately reviewed.

### 3. Run The Phase 6.3 Local Smoke Test

This is the existing Phase 6.3 local API smoke test:

```powershell
python scripts/run_phase_6_3_local_api_smoke_test.py
```

Expected first success line:

```text
Phase 6.3 local API smoke test passed
```

The script launches its own isolated server on `127.0.0.1`, uses temporary
input/output/state locations, runs the minimal workflow, verifies downloads and
public-response safety, and stops that server. It does not validate a reverse
proxy, TLS, authentication, public DNS, or real Coze connectivity.

If the default smoke port is occupied, choose a free loopback port before
rerunning:

```powershell
$env:BIOINFO_SMOKE_TEST_PORT = "8766"
python scripts/run_phase_6_3_local_api_smoke_test.py
```

### 4. Start The Selected Uvicorn Command

Launch the service with its final environment variables and bind choice. Keep
the process logs available to the operator, but do not return logs, tracebacks,
credentials, or environment values through an API response.

## Health And Contract Verification

Check the local upstream first:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The existing response is:

```json
{
  "status": "ok",
  "service": "bioinformatics-agent-backend",
  "phase": "phase-2-api-skeleton"
}
```

The historical `phase` value is part of the existing response. Phase 6.4 does
not change it or any other endpoint response shape.

When a protected proxy is configured, repeat `GET /health` through its approved
HTTPS base URL from an authorized client. Verify the HTTP status, TLS
certificate, service identity, authentication policy, and that the Uvicorn port
is not independently reachable from an untrusted network.

For task-contract verification, confirm that:

- only safe relative input paths are accepted
- an absolute path and a path containing `..` are rejected
- `coze-summary` reports `safe_to_present` only under the existing rules
- artifact downloads use relative `/task/...` API links
- an unknown task or artifact produces the existing safe error response
- no response contains a local absolute path, `file://` URL, traceback,
  password, token, secret, or raw process environment value
- minimal output is described as exploratory CPM/log2FC ranking without
  p-values or adjusted p-values
- DESeq2 is requested only after `GET /task/formal-de/preflight` reports ready

Use synthetic or approved non-sensitive validation inputs. Do not use
unreviewed production data merely to test proxy reachability.

## Current Lifecycle Integration Gate

Phase 6.3 confirms that the current lifecycle guard still requires these
existing preparation calls after input registration and before `POST
/task/run`:

1. `POST /task/plan`
2. `POST /task/qc`

The narrow Phase 6.2 initial endpoint selection does not include those two
calls. Before claiming an end-to-end Coze workflow is ready, the operator and
integration owner must confirm that the reviewed client/tool contract can make
both existing calls in the correct order, or defer publication until that
contract gap is resolved in a later phase.

Phase 6.4 does not remove the lifecycle guard, change the Phase 6.2 endpoint
selection, add a route, or add a public endpoint. A healthy server with this
unresolved integration gap is not a go-live approval.

## Operator Checklist

Record the deployment revision, environment identifier, operator, timestamps,
validation results, and approval evidence alongside this checklist.

### Source And Dependencies

- [ ] The exact application revision is recorded and matches the reviewed
  Phase 6 baseline.
- [ ] The Phase 6.1, 6.2, and 6.3 release tags resolve to their reviewed
  commits, and a previously validated Git tag is recorded for rollback.
- [ ] The working tree or release artifact contains the reviewed
  `requirements.txt` and Phase 6.1 through 6.4 documentation.
- [ ] `python -m pip install -r requirements.txt` completed in the intended
  environment.
- [ ] `python -m pytest -q` passed without skipped safety or contract tests
  being treated as success.

### Filesystem And State

- [ ] `BIOINFO_INPUT_ROOT` points to the intended trusted, readable input
  root.
- [ ] `BIOINFO_OUTPUT_ROOT` points to the intended writable artifact root.
- [ ] `BIOINFO_TASK_STORE_PATH` points to the intended writable SQLite file.
- [ ] Staging and production do not share input, output, or state roots.
- [ ] Input, output, state, repository, and log directories are not served
  directly.
- [ ] Disk capacity, retention, cleanup, and backup ownership are defined.
- [ ] The SQLite task store and matching output artifacts can be backed up and
  restored as one consistent deployment state.

### Launch And Network

- [ ] Local development uses `127.0.0.1` and only local development uses
  `--reload`.
- [ ] The operator launch uses `--workers 1`.
- [ ] A same-host proxy uses `127.0.0.1`, or `0.0.0.0` is restricted to the
  required private proxy/platform network.
- [ ] The Uvicorn port is not directly reachable from an untrusted network.
- [ ] The proxy provides HTTPS/TLS, authentication, authorization, endpoint
  allow-listing, request-size limits, rate limits, and timeouts.
- [ ] Forwarded headers are trusted only from the configured proxy.
- [ ] Access logs and error handling do not disclose credentials, private
  inputs, tracebacks, or local paths.

### Validation And Contract

- [ ] `python scripts/validate_phase_6_2_coze_manifest.py` passed.
- [ ] `python scripts/run_phase_6_3_local_api_smoke_test.py` passed.
- [ ] The final local upstream returned the expected `GET /health` service
  identity.
- [ ] The protected proxy health request passed from an authorized client.
- [ ] The current `POST /task/plan` and `POST /task/qc` prerequisites are
  accounted for in the reviewed integration sequence.
- [ ] Coze-facing responses and downloads were checked for relative API paths
  and absence of local absolute paths.
- [ ] Minimal results retain their exploratory-statistics limitations.
- [ ] DESeq2 is disabled or its preflight and run behavior have been
  deliberately verified.

### Exposure Approval

- [ ] No real Coze credential was used during these Phase 6.4 checks.
- [ ] The Phase 6.2 plugin materials are still identified as draft unless a
  separate publication review has occurred.
- [ ] The operator understands that health alone is not workflow or security
  readiness.
- [ ] A named owner has approved the authentication, privacy, retention,
  monitoring, incident-response, and rollback controls.
- [ ] All unresolved checklist items are documented as go-live blockers, not
  silently accepted.

## Logging And Diagnostics

Keep Uvicorn and reverse-proxy diagnostics in operator-controlled logs. Use
them to investigate startup failures, rejected requests, task lifecycle errors,
and upstream timeouts. Apply access controls, retention limits, and redaction
before logs leave the host.

Public errors must retain the existing safe API shapes. Do not copy exception
stacks, process environment values, credentials, or internal filesystem
locations into `detail` fields or Coze-facing summaries. When escalating an
incident, share sanitized timestamps, status codes, task identifiers, and
operator-observed messages.

## Routine Operation And Monitoring

Without adding new endpoints, the operator should monitor:

- process availability and authenticated `GET /health` results
- proxy 4xx/5xx rates and upstream timeouts
- task failures using sanitized service logs
- free space and write permissions for output and state volumes
- SQLite locking errors
- artifact retention and backup completion
- unexpected attempts to reach unapproved endpoints or the upstream port
- any response-safety report involving a local path, traceback, or credential

Do not log full biological input contents, authorization values, or other
secrets. Monitoring and alerting are deployment controls; Phase 6.4 adds no
monitoring endpoint or runtime dependency.

## Troubleshooting

| Symptom | Likely cause | Operator action |
| --- | --- | --- |
| `No module named uvicorn` or an application import error | Dependencies are missing, the wrong Python environment is active, or the command is not running from the repository root. | Activate the reviewed environment, return to the repository root, run `python -m pip install -r requirements.txt`, and rerun tests. |
| Service not starting | The application import, environment, working directory, dependency installation, or storage initialization failed. | Keep traffic closed, inspect sanitized diagnostics, correct the documented prerequisite, and rerun tests before restart. |
| Address or port already in use | Another process owns port 8000 or the configured smoke-test port. | Identify the owning process, stop it only if authorized, or select an approved free port and update the proxy/upstream configuration consistently. |
| Port conflict persists | The selected replacement port is also occupied or the proxy still points to the previous port. | Select one approved free port, update the Uvicorn and proxy settings together, and repeat local health verification. |
| Local `GET /health` is refused | Uvicorn is stopped, still starting, bound to another address, or listening on another port. | Inspect sanitized process logs and the exact launch command; correct the bind or port before checking the proxy. |
| Local health works but the proxy returns 502, 503, or 504 | The upstream address, firewall rule, proxy timeout, or TLS/proxy routing is wrong. | Keep public traffic closed; verify proxy-to-upstream connectivity and configuration without widening the upstream to the public internet. |
| Missing input files | The expected metadata or count matrix was not staged beneath `BIOINFO_INPUT_ROOT`. | Stage the approved file, verify service-account read access, and register its safe relative path. |
| Unsafe path rejected | The registration request used an absolute path, path traversal, or a path outside `BIOINFO_INPUT_ROOT`. | Correct the request to a safe relative path. Do not relax path validation or widen filesystem access. |
| Input registration is rejected | The file is missing, unreadable, has an unsupported suffix, or the requested input role is invalid. | Correct the staged file or request using the existing contract, then retry registration. |
| Invalid contrast | The contrast column or numerator/denominator is absent, ambiguous, or inconsistent with metadata. | Correct the request using values present in the approved metadata. Do not infer or reverse a comparison silently. |
| Output or SQLite initialization fails | The service account lacks permission, the parent directory is absent, the volume is read-only/full, or the configured path is wrong. | Stop traffic, correct the directory/path/permission or capacity problem, then restart and verify health plus a safe isolated workflow. |
| A task appears missing after restart | `BIOINFO_TASK_STORE_PATH` changed or a non-persistent state volume was used. | Restore the recorded configuration or an approved consistent state/artifact backup; do not create replacement task records by hand. |
| `POST /task/run` is blocked | Required inputs, `POST /task/plan`, or `POST /task/qc` were skipped, or the requested method is not ready. | Follow the existing lifecycle in order and inspect the safe error response. Do not bypass the lifecycle guard. |
| Artifact not found or artifact download returns 404 | The task metadata and `BIOINFO_OUTPUT_ROOT` no longer refer to the same artifact set, the name is wrong, or the artifact is unavailable. | Restore the matching configuration/backup and verify the task artifact listing. Never map the proxy directly to the output directory. |
| DESeq2 preflight reports not ready | R, Rscript, BiocManager, or DESeq2 is unavailable. | Keep using `minimal_cpm_log2fc` or provision the existing optional DESeq2 prerequisites in a separately reviewed change. Do not claim DESeq2 ran. |
| SQLite is locked or tasks are inconsistent across requests | Competing processes/workers or shared state are using the local store unsafely. | Drain traffic and return to one application process with `--workers 1`; do not add a database server as an emergency Phase 6.4 workaround. |
| Manifest validation fails | A draft file is missing, malformed, unsafe, or inconsistent with the reviewed subset. | Keep publication blocked, review the diff and Phase 6.2 contract, and restore or deliberately regenerate the material in a separate reviewed change. |
| A response exposes a local path, traceback, credential, or environment value | A public-response safety boundary has failed. | Remove external traffic immediately, preserve sanitized evidence, revoke any exposed credential, and treat the issue as a release blocker. Do not mask it only at the proxy. |

## Known Limitations

- no frontend
- no real Coze API publication yet
- no public deployment is performed by this phase
- no edgeR
- no limma
- no enrichment analysis
- no built-in production authentication, authorization, rate limiting, or
  upload service
- no multi-worker or multi-node coordination guarantee
- DESeq2 requires local R, Rscript, BiocManager, and DESeq2 readiness
- the Phase 6.3 smoke test does not validate an external reverse proxy or Coze
  connectivity
- the current run lifecycle requires the existing plan and QC preparation
  calls described above

## Shutdown And Rollback

For a planned local shutdown, stop Uvicorn gracefully with `Ctrl+C`. Under a
service manager, use its graceful stop operation and allow in-flight requests
to finish within the approved timeout.

For rollback:

1. Close or drain external traffic at the proxy.
2. Stop the current application process gracefully.
3. Preserve sanitized logs and record the failure and current revision.
4. Select a previously validated Git tag recorded in the release evidence,
   verify the tag and commit identity, and restore that tagged application
   revision through the repository's normal release process. Do not create a
   Phase 6.4 tag as part of this work.
5. Restore the tagged revision's exact environment and proxy configuration.
6. Restore SQLite state and output artifacts as a consistent backup pair only
   when necessary; never indiscriminately delete inputs, outputs, or state.
7. Restart the service with the restored version on an internal bind.
8. Rerun tests appropriate to the restored release, manifest validation,
   `GET /health`, and an isolated contract/smoke check.
9. Reopen traffic only after the rollback owner confirms the original failure
   is absent and the safety checks pass.

Phase 6.4 includes no schema migration, data migration, or runtime change, so
its documentation can be reverted independently. This phase does not create a
new Git tag.

## Safety And Scope Guardrails

Phase 6.4 preserves these boundaries:

- no edgeR implementation
- no limma implementation
- no enrichment analysis
- no frontend code
- no real Coze API call
- no public server deployment requirement
- no Docker runtime requirement
- no Snakemake, Nextflow, or workflow engines
- no database server dependency
- no arbitrary filesystem reads
- no local absolute paths in public API responses
- no traceback/token/password/secret leakage
- relative download URLs only
- no change to existing endpoint response shapes
- no new public API endpoints
- no new Git tag

The only repository changes for this phase are deployment/operator
documentation, a README pointer, and deterministic validation tests.
