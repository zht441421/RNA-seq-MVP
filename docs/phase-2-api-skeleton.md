# Phase 2 API Skeleton

## Project Phase

Phase 2 introduces a minimal FastAPI backend API skeleton for the
Coze-based bioinformatics analysis agent.

Phase 1 Bulk RNA-seq MVP work is complete and preserved separately. This Phase 2
document describes only the current lightweight API skeleton.

## Backend Purpose

The current backend is a small service scaffold intended to provide:

- a health check endpoint for deployment and local validation
- placeholder task creation
- placeholder task status lookup
- deterministic placeholder analysis planning
- deterministic placeholder QC planning
- deterministic placeholder task run completion
- a stable starting point for later Coze workflow integration

It does not run real RNA-seq analysis yet.

## Implemented Endpoints

### GET `/health`

Checks whether the FastAPI service is running.

Expected response example:

```json
{
  "status": "ok",
  "service": "bioinformatics-agent-backend",
  "phase": "phase-2-api-skeleton"
}
```

### POST `/task/create`

Creates a placeholder in-memory task.

Request body:

```json
{}
```

Expected response example:

```json
{
  "task_id": "task_xxx",
  "status": "created",
  "message": "Task created. Real RNA-seq analysis is not implemented yet."
}
```

### POST `/task/plan`

Creates a deterministic placeholder analysis plan. This endpoint is intended
for Phase 2 API integration only and does not run DESeq2, edgeR, limma, or any
RNA-seq computation.

Request body:

```json
{
  "project_name": "demo_bulk_rnaseq",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "analysis_goal": ["qc", "differential_expression"],
  "group_column": "condition",
  "contrast": "treatment_vs_control"
}
```

Expected response example:

```json
{
  "project_name": "demo_bulk_rnaseq",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "status": "planned",
  "recommended_workflow": [
    {
      "order": 1,
      "name": "Input review",
      "description": "Confirm project 'demo_bulk_rnaseq' uses bulk_rnaseq data at the count_matrix level.",
      "status": "planned"
    }
  ],
  "reliability_notes": [
    "This is a deterministic placeholder plan for API integration only.",
    "No real DESeq2, edgeR, limma, or RNA-seq execution is performed by this endpoint.",
    "Future execution should validate files, metadata, design formula, and runtime environment before analysis."
  ]
}
```

### POST `/task/qc`

Creates a deterministic placeholder QC plan for a Bulk RNA-seq task request.
This endpoint is intended for Phase 2 API integration only and does not read
files, validate count matrices, or run RNA-seq QC.

Request body:

```json
{
  "project_name": "demo_bulk_rnaseq",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "metadata_file": "metadata.csv",
  "count_matrix_file": "counts.csv",
  "sample_id_column": "sample_id",
  "group_column": "condition",
  "contrast": "treatment_vs_control"
}
```

Expected response example:

```json
{
  "project_name": "demo_bulk_rnaseq",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "status": "qc_planned",
  "qc_checks": [
    {
      "check_id": "qc_1",
      "name": "File availability check",
      "description": "Confirm metadata and count matrix files are provided.",
      "status": "planned",
      "required": true
    },
    {
      "check_id": "qc_2",
      "name": "Sample ID matching check",
      "description": "Plan validation that sample IDs in metadata match count matrix columns.",
      "status": "planned",
      "required": true
    },
    {
      "check_id": "qc_3",
      "name": "Group column check",
      "description": "Plan validation that the group column exists and supports the requested contrast.",
      "status": "planned",
      "required": true
    },
    {
      "check_id": "qc_4",
      "name": "Count matrix structure check",
      "description": "Plan validation for gene-by-sample count matrix structure and numeric count values.",
      "status": "planned",
      "required": true
    }
  ],
  "reliability_gates": [
    "metadata_file_provided",
    "count_matrix_file_provided",
    "sample_id_column_defined",
    "group_column_defined",
    "contrast_defined"
  ],
  "limitations": [
    "This endpoint currently returns a QC planning skeleton only.",
    "No real file reading or count matrix validation is performed yet.",
    "Actual QC execution will be implemented in a later phase."
  ]
}
```

### POST `/task/run`

Returns a deterministic placeholder task run result. This endpoint is intended
for Phase 2 API integration only and does not read files, write files, run QC,
or execute DESeq2, edgeR, limma, FastQC, or MultiQC.

Request body:

```json
{
  "task_id": "task_demo",
  "project_name": "demo_bulk_rnaseq",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "analysis_goal": ["qc", "differential_expression"],
  "group_column": "condition",
  "contrast": "treatment_vs_control"
}
```

Expected response example:

```json
{
  "task_id": "task_demo",
  "project_name": "demo_bulk_rnaseq",
  "status": "run_placeholder_completed",
  "run_steps": [
    {
      "step_id": "run_1",
      "name": "Load task configuration",
      "status": "completed",
      "message": "Task configuration received."
    },
    {
      "step_id": "run_2",
      "name": "QC execution placeholder",
      "status": "completed",
      "message": "QC execution is not implemented yet."
    },
    {
      "step_id": "run_3",
      "name": "Differential expression placeholder",
      "status": "completed",
      "message": "DESeq2, edgeR, and limma execution are not implemented yet."
    }
  ],
  "artifacts": [],
  "limitations": [
    "This endpoint does not run real RNA-seq analysis.",
    "No files are read or written.",
    "No statistical or biological conclusion should be drawn from this placeholder response."
  ]
}
```

### GET `/task/{task_id}/status`

Returns the current status of a previously created in-memory task.

Expected response example:

```json
{
  "task_id": "task_xxx",
  "status": "created",
  "message": "Task created. Real RNA-seq analysis is not implemented yet."
}
```

If the task ID is unknown, the API returns `404`.

## Start the Server

First enter the correct working directory:

```powershell
cd "D:\coze agent\bioinformatics-agent"
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the FastAPI server:

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8010
```

Open the interactive API documentation:

```text
http://127.0.0.1:8010/docs
```

## Test `/health`

```powershell
cd "D:\coze agent\bioinformatics-agent"
Invoke-RestMethod http://127.0.0.1:8010/health
```

## Create a Task

```powershell
cd "D:\coze agent\bioinformatics-agent"
$task = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/task/create `
  -ContentType "application/json" `
  -Body '{}'

$task
```

## Create an Analysis Plan

```powershell
cd "D:\coze agent\bioinformatics-agent"
$body = @{
  project_name = "demo_bulk_rnaseq"
  omics_type = "bulk_rnaseq"
  input_level = "count_matrix"
  analysis_goal = @("qc", "differential_expression")
  group_column = "condition"
  contrast = "treatment_vs_control"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/task/plan `
  -ContentType "application/json" `
  -Body $body
```

## Create a QC Plan

```powershell
cd "D:\coze agent\bioinformatics-agent"
$body = @{
  project_name = "demo_bulk_rnaseq"
  omics_type = "bulk_rnaseq"
  input_level = "count_matrix"
  metadata_file = "metadata.csv"
  count_matrix_file = "counts.csv"
  sample_id_column = "sample_id"
  group_column = "condition"
  contrast = "treatment_vs_control"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/task/qc `
  -ContentType "application/json" `
  -Body $body
```

## Run a Task Placeholder

```powershell
cd "D:\coze agent\bioinformatics-agent"
$body = @{
  task_id = "task_demo"
  project_name = "demo_bulk_rnaseq"
  omics_type = "bulk_rnaseq"
  input_level = "count_matrix"
  analysis_goal = @("qc", "differential_expression")
  group_column = "condition"
  contrast = "treatment_vs_control"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/task/run `
  -ContentType "application/json" `
  -Body $body
```

## Check Task Status

```powershell
cd "D:\coze agent\bioinformatics-agent"
Invoke-RestMethod http://127.0.0.1:8010/task/$($task.task_id)/status
```

Or replace the task ID manually:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/task/task_xxx/status
```

## Current Limitations

- Tasks are stored only in memory.
- Task state is lost when the server restarts.
- No real RNA-seq analysis is executed.
- The QC endpoint returns a planning skeleton only.
- The QC endpoint does not read metadata or count matrix files yet.
- The QC endpoint does not perform real Bulk RNA-seq QC yet.
- The run endpoint returns a placeholder completion result only.
- The run endpoint does not read or write files.
- The run endpoint does not run DESeq2, edgeR, limma, FastQC, or MultiQC.
- The run endpoint does not produce artifacts or biological conclusions.
- No file upload API is implemented in this Phase 2 skeleton.
- No database, object storage, queue, authentication, or authorization is wired
  into the task API.
- The task API currently returns placeholder task status, analysis plans, QC
  plans, and run results only.

## Next Planned API Extensions

Likely next API additions include:

- file registration or upload endpoints
- persistent task storage
- task queue integration
- analysis run dispatch
- artifact/result lookup endpoints
- structured error reporting for invalid input
- Coze-facing workflow adapter endpoints

## Coze Integration Notes

Coze can eventually call this backend as an external API service.

For the current skeleton:

- Coze can call `GET /health` to verify backend availability.
- Coze can call `POST /task/create` to create a placeholder task.
- Coze can call `POST /task/plan` to request a deterministic placeholder
  analysis plan.
- Coze can call `POST /task/qc` to request a deterministic placeholder QC plan.
- Coze can call `POST /task/run` to request a deterministic placeholder run
  result.
- Coze can call `GET /task/{task_id}/status` to poll task status.
- The current API is not yet connected to real Bulk RNA-seq analysis.
- Future Coze workflows should treat returned tasks as placeholders until
  analysis dispatch and artifact APIs are implemented.
