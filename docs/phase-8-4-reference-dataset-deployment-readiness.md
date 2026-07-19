# Phase 8.4 Reference Dataset and Deployment Readiness

## Purpose and status

Phase 8.4 establishes repeatable scientific-boundary and engineering regression
baselines while preparing a protected deployment gate for the existing Coze
tool contracts. It adds no API route and changes no RNA-seq or DESeq2 behavior.

No real Coze deployment or publication was performed. No staging or production
endpoint was created, and no real credential was stored. This phase does not
prove scientific validity. Its synthetic fixture validates workflow behavior
only and must not be presented as scientific evidence.

## Reference dataset classification

The versioned classification model is documented in
`reference-datasets/README.md`:

- `workflow_fixture` is synthetic or miniature workflow-test data;
- `reference_dataset` is provenance- and checksum-controlled technical data;
- `scientific_benchmark_dataset` is real public data with reviewed provenance,
  usage terms, benchmark purpose, and scientific limitations.

The initial `phase-8-4-rnaseq-minimal-synthetic-v1` entry is a synthetic
`workflow_fixture`, has six samples and ten genes, and is explicitly unsuitable
for scientific validation.

## Manifest and Golden Result structure

`reference-dataset-manifest.json` records stable dataset identity, type,
classification, nature, source/accession fields, usage terms, SHA-256 protected
files, input schemas, contrast, expected counts, purpose, limitations,
scientific suitability, and Golden Result location.

Golden Results specify behavior rather than biological truth. Stable values
such as method, comparison direction, boolean method flags, fixed fixture
counts, and terminal lifecycle status use exact checks. Artifact categories use
set inclusion, counts may use inclusive ranges, and safety fields use presence
or accepted-value checks. Request IDs, timestamps, artifact order,
floating-point tables, software versions, and DESeq2 numeric output are not
byte-for-byte expectations. DESeq2 remains environment-dependent and a success
may be asserted only after real preflight and execution succeed.

The minimal workflow Golden Result requires exploratory boundaries, no
p-values, no adjusted p-values, no unsupported enrichment, no significance
claim, and no causation claim.

## Offline validation workflow

Run:

```text
python scripts/verify_phase_8_4_reference_dataset_readiness.py
```

The verifier checks documentation, JSON parsing, manifest schema, local fixture
existence and checksums, dataset classification and limitations, Golden Result
schema and boundaries, seven-tool Manifest/OpenAPI compatibility, unique live
operation IDs, plugin mapping, safe deployment material, and the full pytest
suite. `--skip-tests` is available only for a fast structural check.

Normal tests and this verifier require no network, Coze account, cloud service,
external secret, or public deployment.

## Coze plugin package preparation status

`deployment/phase-8-4-coze-plugin-package.json` is an offline mapping of the
seven reviewed tool names to their live operation IDs. It contains no base URL
or credential and is marked `preparation_only_not_published`. It is not an
installable or published Coze plugin and grants no deployment authorization.

Before staging, configure one externally reviewed HTTPS base URL. Localhost,
loopback, private development URLs, plain HTTP, URL query credentials, and
embedded API keys are forbidden. The API key must be injected through Coze
Secrets or an equivalent deployment secret store and sent only in the reviewed
`X-Bioinfo-API-Key` header.

## Reverse proxy and trust assumptions

The reverse proxy must terminate TLS, preserve the request body and correlation
header behavior, apply explicit forwarded-header trust, restrict administrative
paths, enforce upstream timeouts without unsafe application cancellation, and
avoid logging credentials or full sensitive payloads. The current application
does not implement trusted-proxy allowlists; proxy trust is therefore a manual
staging gate and deployment-layer responsibility.

## Environment configuration contract

The safe example is `examples/deployment/phase-8-4.env.example`.

Currently implemented settings:

- `BIOINFO_REQUIRE_API_KEY`, `BIOINFO_API_KEY`, `BIOINFO_API_KEY_HEADER`;
- request limits: `BIOINFO_MAX_REQUEST_BYTES`, timeout and input-specific limit
  settings;
- rate limiting: `RATE_LIMIT_ENABLED`, request/window/scope/exempt settings;
- `BIOINFO_INPUT_ROOT`, `BIOINFO_OUTPUT_ROOT`, `BIOINFO_TASK_STORE_PATH`;
- runner selections including `RUN_MODE`, Rscript and Docker settings.

Planned recommendations only—not consumed by current runtime code—are clearly
marked for public base URL, environment name, logging level, trusted proxy mode,
and data retention. Documenting a planned variable does not make it functional.

## Logging, secret redaction, and artifact isolation

Structured request logs must retain opaque request IDs while excluding API key
values, registered file contents, local roots, commands, and exception traces.
Unexpected errors must remain sanitized. Execution trace failure reasons remain
bounded safe identifiers.

Inputs and artifacts remain task-scoped. Public summary/download references are
relative API paths. A download must use an artifact name returned for the same
task; traversal, absolute paths, missing artifacts, and cross-task reads remain
rejected. Storage roots must not be placed under a public web root.

## Rollback requirements

Before staging, record the deployed commit and image/runtime version, preserve
the previous known-good version, back up or snapshot task metadata according to
the approved retention policy, verify schema compatibility, and define a fast
route back to the previous version. After rollback, run health, authentication,
task isolation, audit, and minimal workflow smoke checks. Never roll back by
discarding user data or repository changes.

## Deployment readiness gate

Automated pass/fail checks:

- [ ] Full pytest suite passes.
- [ ] Phase 8.4 offline verifier passes.
- [ ] Reference manifest and all Golden Results parse and validate.
- [ ] Local fixture files exist and their SHA-256 checksums match.
- [ ] Scientific boundaries and synthetic-data limitations are present.
- [ ] Live OpenAPI parses and has unique operation IDs.
- [ ] All seven Coze tool bindings and plugin mappings match live OpenAPI.
- [ ] Deployment package contains no credential, absolute local path,
  localhost/loopback URL, or insecure production URL.
- [ ] Authentication, artifact-isolation, audit, and regression tests pass.

Manual staging gates:

- [ ] Approve the externally configured HTTPS base URL and certificate chain.
- [ ] Verify API key injection through Coze Secrets/deployment secret storage.
- [ ] Review reverse-proxy forwarded-header trust and network allowlists.
- [ ] Review log routing, access restrictions, redaction, and retention.
- [ ] Approve artifact/input mounts, permissions, backup, deletion, and data
  retention policy.
- [ ] Exercise rollback from the candidate to the recorded known-good version.
- [ ] Obtain explicit authorization before any Coze publication or staging
  deployment.

Failure of any automated or applicable manual gate blocks staging.

## Staging entry criteria

Staging may begin only after the automated gate is green, every applicable
manual gate has an owner and evidence, a trusted HTTPS base URL exists outside
the repository, real credentials are provisioned outside source control,
rollback has been rehearsed, and explicit deployment authorization is granted.

## Explicit non-goals

- No Coze publication, real plugin installation, staging deployment, or public
  production endpoint.
- No LLM behavior change, new analysis algorithm, DESeq2 behavior change,
  enrichment, batch correction, or scientific benchmark claim.
- No Redis, Celery, Kubernetes, workflow engine, object storage, cloud service,
  or production task queue.
- No new runtime behavior for planned environment settings.
