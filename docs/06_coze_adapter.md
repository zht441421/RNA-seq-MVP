# Coze Adapter Workflow

The Coze adapter exposes high-level APIs under `/coze`. Coze remains the user
interaction layer. The backend owns file inspection, QC, method recommendation,
user-confirmed execution, evidence package generation, reliability grading, and
audit logs.

Current MVP limitation: Coze file upload is not implemented. Coze should pass
local file paths to the backend as a placeholder. Later this can be replaced by
upload handling backed by object storage such as MinIO or S3.

## Recommended Workflow

1. Create Project
2. Register/Inspect Files
3. User Confirms Schema Mapping
4. Prepare Analysis: QC + Plan
5. User Confirms Plan
6. Confirm and Run
7. Show Status
8. Show Report + Artifact Manifest

## API Nodes

### 1. Create Project

Call:

```text
POST /coze/projects
```

User provides:

- Project name.
- Omics type: currently `bulk_rnaseq`.
- Input level: currently `count_matrix`.
- Organism.
- Gene ID type.
- Annotation version.

Coze should display:

- `project_id`
- `human_readable_summary`
- `next_action`

Next action: `upload_or_register_files`.

### 2. Register/Inspect Files

Call:

```text
POST /coze/projects/{project_id}/inspect
```

User provides:

- `count_matrix_path`
- `metadata_path`

Coze should display:

- Candidate gene ID columns.
- Count matrix sample columns.
- Metadata columns.
- Possible sample ID column.
- Possible group column.
- Possible batch column.
- Warnings.

Next action: `confirm_schema_mapping`.

### 3. User Confirms Schema Mapping

Coze must ask the user to confirm:

- `gene_id_column`
- `sample_id_column`
- `group_column`
- `reference_group`
- `test_group`
- optional `batch_column`
- optional `covariates`
- FDR threshold
- log2FC threshold

### 4. Prepare Analysis

Call:

```text
POST /coze/projects/{project_id}/prepare-analysis
```

Backend actions:

- Stores schema mapping.
- Runs QC.
- If stop conditions exist, returns `next_action: fix_input`.
- If QC can continue, generates a recommended analysis plan.

Coze should display:

- QC status.
- Stop conditions.
- Warnings.
- Recommended plan.
- Whether user confirmation is required.

Next action is `confirm_and_run` or `fix_input`.

### 5. User Confirms Plan

Coze must explicitly ask the user to confirm the recommended plan before
execution. The backend will not run if `confirmed=false`.

### 6. Confirm and Run

Call:

```text
POST /coze/projects/{project_id}/confirm-and-run
```

User provides:

- `confirmed`
- optional `run_mode`: `mock`, `real_r`, or `docker_r`
- optional analysis plan overrides

Backend actions:

- Refuses to run if the plan is not confirmed.
- Refuses to run if QC stop conditions exist.
- Uses default backend `RUN_MODE` if `run_mode` is omitted.
- Generates an evidence package after run completion or runner failure.

Coze should display:

- Run status.
- Reliability grade.
- Allowed conclusion level.
- Human-readable summary.
- Artifact manifest.

Next action: `review_report`.

### 7. Show Status

Call:

```text
GET /coze/projects/{project_id}/status
```

Use this for polling. Coze should display:

- Project status.
- Current stage.
- Run status.
- Reliability grade.
- Human-readable summary.
- Next action.

### 8. Show Report + Artifact Manifest

Call:

```text
GET /coze/projects/{project_id}/report
```

Coze should display:

- `summary_markdown`
- `qc_report_markdown`
- `method_selection_markdown`
- `reliability_report_markdown`
- audit log summary
- artifact manifest
- allowed conclusion level
- `strong_conclusion_allowed`

The markdown content is read from the evidence package. The report endpoint
does not generate new scientific conclusions.

## Reliability Display Rules

If the reliability grade is C, D, or E:

- Coze must display the risk warning prominently.
- `strong_conclusion_allowed` must be false.
- Coze must not phrase results as definitive biological or clinical findings.
- Coze must show that current evidence is insufficient for a strong scientific
  conclusion.

Allowed conclusion levels:

- A: statistical conclusions may be stated with limitations; causal language is
  prohibited.
- B: only cautious supportive conclusions are allowed.
- C: exploratory findings only.
- D: not recommended for formal conclusions.
- E: no scientific conclusion.

## Current Non-Goals

- No real Coze file upload.
- No MinIO or S3.
- No FASTQ processing.
- No Nextflow or Snakemake.
- No other omics types.
- No automatic R package installation.

