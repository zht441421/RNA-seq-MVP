# Phase 8.6.1 Containerized R / DESeq2 Runtime Enablement

## Purpose and baseline

Phase 8.6.1 starts from commit `91bbe0a283fa6e66141e00ae8e2d76aa84c6a665`
and tag `phase-8-6-reference-dataset-validation`. It adds a fixed,
build-time-installed R/Bioconductor/DESeq2 runtime to the existing Phase 8.5
single application container so the existing DESeq2 preflight can report real
readiness.

Container runtime readiness is necessary but not sufficient for scientific
validation. This phase does not run or freeze a real-public-data DESeq2
scientific baseline. That work remains Phase 8.6.2.

## Architecture decision

Approach B was selected: retain the digest-pinned Python 3.12.10 slim-bookworm
base and install fixed Debian R/Bioconductor packages during image build. This
preserves the existing Python ABI, non-root UID/GID, read-only root filesystem,
entrypoint, healthcheck, Compose topology, TLS proxy, and operational rollback.

Approach A, migrating the application onto an official Bioconductor image, was
rejected for this phase because it would replace the established Python base,
require revalidating user and entrypoint conventions, enlarge the migration
surface, and provide no benefit to the single-process FastAPI-to-Rscript path.
No R microservice or additional network service is introduced.

## Frozen runtime

The authoritative machine-readable contract is
`docs/runtime/r-deseq2-runtime.json`. The application base is
`python:3.12.10-slim-bookworm` at the recorded SHA-256 digest. It uses Debian 12
Bookworm snapshot `20250601T000000Z`, Python 3.12.10, R/Rscript 4.2.2,
Bioconductor 3.16, BiocManager 1.30.20, and DESeq2 1.38.3. Core package and
system-library versions are recorded from the built image.

The snapshot repository and exact top-level Debian package versions make
installation failures fatal and fix the dependency source. No `latest`,
`devel`, rolling alias, CRAN source install, or `BiocManager::install` is used.
Package indexes and apt caches are removed after the build.

## Build and runtime process

```text
docker build --pull=false --build-arg VCS_REF=phase-8-6-1-uncommitted -t bioinformatics-agent-api:phase-8-6-1-local .
python scripts\probe_phase_8_6_1_r_deseq2_runtime.py --json
```

The Dockerfile fails unless R and Rscript execute, all declared packages load,
every R package version matches, and Bioconductor reports 3.16. Startup and task
execution perform no package installation. R libraries are system-owned and
readable but not writable by UID/GID `10001:10001`; no writable user library is
required. `R_ENVIRON_USER` and `R_PROFILE_USER` are disabled to prevent runtime
profile mutation.

The ordinary HTTP healthcheck remains a lightweight FastAPI liveness check. R
readiness is evaluated separately by the runtime probe and existing
`GET /task/formal-de/preflight` boundary.

## Preflight and controlled execution

The preflight still verifies R/Rscript execution and BiocManager/DESeq2. It now
also loads the required dependency set through the project-controlled
`deseq2_runtime_preflight.R`, checks the frozen version manifest when configured,
and verifies temporary and output workspace writability. It does not execute a
differential-expression analysis.

The formal executor continues to use its existing hard-coded DESeq2 R program
and unchanged statistical statements, design and contrast. User-supplied R code
is never evaluated. Validated paths and contrast values are separate argument
list entries; `shell=False` is enforced; the subprocess working directory is
the task-specific output directory; timeout remains 120 seconds; non-zero exit,
timeout, malformed output, missing output, and permission failures remain safe
failure states. Public stderr is bounded by subprocess completion and sanitized
before exposure.

## Staging security and filesystem

The architecture remains FastAPI plus container-local Rscript in one non-root
application container behind the existing Nginx TLS proxy. FastAPI is not
published directly. API-key secret injection, loopback-only ports, dropped
capabilities, `no-new-privileges`, read-only root filesystem, persistent SQLite
and artifact volumes, task-scoped artifact APIs, and the Phase 8.6 read-only
reference-data mount remain intact.

The runtime probe verifies:

- UID/GID are non-root and Rscript inherits the same identity;
- application source and installed R libraries are not writable;
- `/tmp`, task/artifact workspace, and database directory are writable;
- no R package installation is attempted or required.

Task isolation is enforced by validated task identifiers, task-scoped output
paths and artifact download authorization. This is a single-process staging
boundary, not an OS sandbox per task; controlled R code receives only validated
task inputs and its own output path.

## Resources, failures and rollback

Local staging configures 4 GiB memory, 2 CPUs and 256 PIDs for the application
container. These are Docker-local limits, not production capacity claims. The
Lightweight preflight subprocess checks use a 20-second timeout; the
controlled full-package-load readiness probe uses 30 seconds to accommodate a
cold start under the configured resource limits. Formal R task subprocess and
HTTP request timeouts remain 120 seconds.
The `/tmp` tmpfs is 64 MiB; task artifacts and SQLite state use named volumes.
Large designs may exhaust CPU, memory, temporary disk or timeout and must fail
without being described as successful analysis.

Failure modes include missing executables/packages/dependencies, version drift,
unwritable runtime directories, denied subprocess creation, timeout, non-zero R
exit, missing result files and malformed results. Rollback is the Phase 8.6 tag
and previous `phase-8-5-local` image; stop the stack, select the previous image,
and restart without deleting persistent volumes.

## Verification

```text
python scripts\verify_phase_8_6_1_containerized_r_deseq2_runtime.py --offline
python scripts\verify_phase_8_6_1_containerized_r_deseq2_runtime.py --docker
```

Docker mode builds the image, starts protected staging, checks health, runtime
versions, non-root/read-only permissions and existing preflight readiness, runs
the Phase 8.5 smoke, repeats readiness after restart, and—when the ignored cache
is present—runs the unchanged Phase 8.6 minimal real-data validation. It never
runs the Phase 8.6 public datasets through DESeq2.

## Non-goals and Phase 8.6.2 entry criteria

No Coze integration occurred. No remote or production deployment occurred. No
Phase 8.6 Golden Result was rewritten. No real DESeq2 public-dataset scientific
baseline was frozen. Package availability and successful loading do not prove
scientific validity.

Phase 8.6.2 remains required to define a separately reviewed real-data DESeq2
execution plan, tolerances, scientific boundaries and Golden Results. It may
start only after Phase 8.6.1 image, probe, preflight, security, restart, prior
regression and full pytest gates have passed and the phase is explicitly
approved.
