# Phase 6.2 Coze Plugin Manifest Preparation

Phase 6.2 is plugin/manifest preparation for a future Coze integration. It
builds on the Phase 6.1 API deployment contract by adding draft metadata,
endpoint selection notes, tool instructions, and validation helpers. It does not
change runtime behavior, add backend endpoints, publish a Coze plugin, call real
Coze APIs, add frontend code, or require public deployment.

## Purpose

The purpose of this phase is to make the existing backend easier to configure
later as a Coze plugin or API tool. The materials in this phase help a future
publisher decide which endpoints to expose, how user concepts map to API
fields, how results should be described, and where the current safety boundaries
are.

## Relationship To Phase 6.1

Phase 6.1 documented the deployable backend contract: startup command,
environment variables, directory layout, endpoint sequence, example payloads,
artifact download behavior, and Coze-facing response boundaries.

Phase 6.2 does not replace that contract. It adds plugin-oriented draft
materials that reference the same backend lifecycle and the same safety rules.

## Recommended Coze Tool Name

Recommended internal tool name:

```text
bioinformatics_rnaseq_task_api
```

Recommended display name:

```text
Bulk RNA-seq Task API
```

## Short Description For Coze

Create, run, monitor, and summarize task-scoped Bulk RNA-seq count matrix
analyses through the existing backend API.

## Long Description For Coze

This tool helps a Coze workflow call a backend Bulk RNA-seq task lifecycle API.
It can create a task, register metadata and count matrix inputs by safe relative
path, run the minimal CPM/log2FC workflow, optionally request DESeq2 when local
preflight readiness passes, check task status, fetch a Coze-safe summary, and
provide relative artifact download links. It does not perform file upload,
public hosting, frontend rendering, enrichment analysis, edgeR, limma, or
biological interpretation beyond documented result boundaries.

## Endpoint Selection Strategy

The initial plugin should expose only the task lifecycle endpoints needed for a
safe, narrow integration:

- health check
- task creation
- input registration
- minimal or DESeq2 task run
- status polling
- Coze-safe summary
- artifact listing
- artifact download
- DESeq2 preflight

Planning, QC, audit, report, project-level, and legacy Coze adapter endpoints
can remain optional or internal until a future publishing phase decides they are
needed.

## Recommended Endpoint Sequence

1. `POST /task/create`
2. `POST /task/{task_id}/inputs/register`
3. `POST /task/run`
4. `GET /task/{task_id}/status`
5. `GET /task/{task_id}/coze-summary`
6. `GET /task/{task_id}/artifacts/{artifact_name}/download`

For DESeq2, call `GET /task/formal-de/preflight` before `POST /task/run`.
This DESeq2 preflight check is the gate for claiming that DESeq2 execution is
available.

## Essential Endpoints For Initial Coze Integration

- `GET /health`
- `POST /task/create`
- `POST /task/{task_id}/inputs/register`
- `POST /task/run`
- `GET /task/{task_id}/status`
- `GET /task/{task_id}/coze-summary`
- `GET /task/{task_id}/artifacts/{artifact_name}/download`

These endpoints are enough to create a task, bind known inputs, run the current
workflow, report status, summarize the result, and present download links.

## Optional Or Supporting Endpoints

- `GET /task/formal-de/preflight` is required only when the user requests
  DESeq2.
- `GET /task/{task_id}/artifacts` is useful for listing available artifacts
  before download.
- `POST /task/plan` and `POST /task/qc` may be used by richer clients, but they
  are not required for the initial plugin manifest draft.

## Request Field Descriptions

- `task_type`: optional task classification for `POST /task/create`.
- `parameters`: optional client metadata for task creation.
- `task_id`: backend task identifier returned by `POST /task/create`.
- `input_role`: either `metadata` or `count_matrix`.
- `source_relative_path`: safe path under the configured input root.
- `project_name`: user-facing project label.
- `omics_type`: currently `bulk_rnaseq` for this contract.
- `input_level`: currently `count_matrix` for this contract.
- `analysis_goal`: requested workflow goals, such as `qc` and
  `differential_expression`.
- `group_column`: metadata column that defines comparison groups.
- `contrast`: human-readable contrast label.
- `execution_mode`: `minimal_real` for minimal workflow or `formal_de_real` for
  DESeq2.
- `analysis_method`: `minimal_cpm_log2fc` or `deseq2`.
- `formal_de_method`: `deseq2` only when DESeq2 is requested.
- `contrast_column`: metadata column used for the explicit comparison.
- `contrast_numerator`: group represented by positive log2FC direction.
- `contrast_denominator`: reference group for the explicit comparison.

## Response Field Descriptions

- `status`: task or run lifecycle status.
- `message`: short task lifecycle message.
- `safe_relative_path`: accepted input path without local absolute path
  exposure.
- `registered`: whether input registration succeeded.
- `next_required_inputs`: remaining input roles needed before run.
- `run_steps`: deterministic summary of execution steps.
- `artifacts`: generated or planned task-scoped artifacts.
- `download_links`: relative API paths for artifact downloads.
- `summary_message`: Coze-safe result summary.
- `contrast`: resolved comparison direction and related fields.
- `positive_log2fc_interpretation`: what positive log2FC means for the
  numerator and denominator.
- `negative_log2fc_interpretation`: what negative log2FC means for the
  numerator and denominator.
- `warnings`: safe caveats for the user.
- `limitations`: method and interpretation boundaries.
- `safe_to_present`: whether the summary is intended for Coze-facing display.

The contrast direction must be explained from `contrast_numerator` and
`contrast_denominator` whenever those fields are present.

## Error Handling Guidance

Coze should present backend errors conservatively:

- Unknown task: tell the user the task could not be found and suggest creating
  or selecting a valid task.
- Missing input: request both metadata and count matrix registration before
  running.
- Invalid contrast: ask the user to confirm the comparison column, treatment
  group, and control group exactly as they appear in metadata.
- Artifact not found: explain that the artifact is not available for this task.
- DESeq2 preflight not ready: explain that local R, Rscript, BiocManager, or
  DESeq2 readiness is incomplete and that DESeq2 was not run.

Do not expose internal stack details, deployment paths, or raw command output in
user-facing wording.

## Safety Boundaries

- no local absolute paths in Coze-facing responses
- no arbitrary filesystem reads
- no raw internal error dumps or credential leakage
- no real Coze API call in this phase
- no frontend in this phase
- no new public API endpoints in this phase
- no public deployment requirement in this phase
- artifact download URLs are relative API paths only
- registered inputs must remain under the configured input root
- generated artifacts must remain under the configured output root

## Known Limitations

- The manifest files are draft preparation files, not a published Coze plugin.
- No real Coze publication is included.
- No public server deployment is included.
- No authentication or authorization layer is added.
- No file upload endpoint is added.
- The minimal workflow is exploratory and does not provide p-values.
- DESeq2 requires preflight readiness before execution.
- No edgeR, limma, enrichment, pathway analysis, batch correction, or complex
  design formula is added.

## Recommended Coze System Or Tool Instructions

Use the backend as a task lifecycle API, not as a source of final biological
claims. Create a task before registering inputs. Register metadata and count
matrix inputs with safe relative paths only. Use `minimal_cpm_log2fc` unless the
user explicitly requests DESeq2 and preflight readiness passes. Always fetch
`coze-summary` before presenting results. Explain log2FC direction from
`contrast_numerator` and `contrast_denominator`. Present artifact downloads as
relative API links or links generated by the deployment layer. Repeat warnings
and limitations when summarizing results.

## What Coze May Say

- A task was created, if the create response succeeded.
- Metadata or count matrix input was registered, if registration succeeded.
- The minimal workflow completed, if the run response reports completion.
- DESeq2 completed only if the DESeq2 run response reports completion.
- Positive log2FC means higher in the numerator group relative to the
  denominator group, when explicit contrast fields are available.
- Downloadable artifacts are available through relative API paths returned by
  the backend.
- Minimal workflow results are exploratory CPM/log2FC rankings.

## What Coze Must Not Claim

- Do not claim biological significance without user validation.
- Do not claim enrichment if enrichment was not run.
- Do not claim p-values for the minimal workflow.
- Do not claim DESeq2 ran if preflight was not ready or the run did not
  complete.
- Do not claim edgeR, limma, GO, KEGG, or GSEA output in this phase.
- Do not present clinical, causal, or pathway-level conclusions from these
  outputs alone.

## Future Work For Real Coze Publishing

Future publishing work can add a public base URL, authentication policy,
deployment-specific OpenAPI import settings, real Coze plugin configuration,
input upload handling, user permission design, rate limits, retention rules,
and operational monitoring. Those items are intentionally outside Phase 6.2.
