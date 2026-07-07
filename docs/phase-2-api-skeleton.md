# Phase 2 API Skeleton

## Project Phase

Phase 2 introduces a minimal FastAPI backend API skeleton for the
Coze-based bioinformatics analysis agent.

Phase 1 Bulk RNA-seq MVP work is complete and preserved separately. This Phase 2
document describes only the current lightweight API skeleton.

For the Phase 2 completion baseline, including the frozen endpoint inventory,
test inventory, OpenAPI snapshot notes, placeholder limitations, and Phase 3
direction, see [Phase 2 API Contract Baseline Completion](phase-2-completion-baseline.md).

## Backend Purpose

The current backend is a small service scaffold intended to provide:

- a health check endpoint for deployment and local validation
- placeholder task creation
- placeholder task status lookup
- deterministic placeholder analysis planning
- deterministic placeholder QC planning
- deterministic placeholder task run completion
- deterministic placeholder task report responses
- deterministic placeholder artifact lists
- deterministic placeholder audit trails
- a stable starting point for later Coze workflow integration

It does not run real RNA-seq analysis yet.

## Phase 2 Placeholder Lifecycle Contract

The current task lifecycle endpoints are placeholder/skeleton contracts for
front-end and Coze API contract sampling only:

- `POST /task/plan`
- `POST /task/qc`
- `POST /task/run`
- `GET /task/{task_id}/report`
- `GET /task/{task_id}/artifacts`
- `GET /task/{task_id}/audit`

The lifecycle contract target is that each endpoint returns deterministic
placeholder payloads and echoes the same `task_id` for a task lifecycle.
Phase 2.9 closes the earlier `plan`/`qc` lifecycle contract gap by allowing
`POST /task/plan` and `POST /task/qc` requests to include an optional `task_id`
and by echoing that value in their placeholder responses when supplied. This is
still a skeleton contract field only; it does not create persistence, shared
state, queueing, or real task execution.

For all Phase 2 lifecycle endpoints, the current placeholder boundary is:

- no real input files are read
- no real log files are written
- no database or durable task/audit storage is written
- no real artifacts are generated
- no real Coze call is made
- no RNA-seq pipeline is run
- responses are deterministic contract samples, not evidence that a real task
  executed

Endpoint-specific placeholder boundaries:

- `plan` does not execute a real planning engine.
- `qc` does not read real QC files, metadata files, or count matrices.
- `run` does not start a real runner.
- `report` returns placeholder report information only, not a generated real
  report.
- `artifacts` returns placeholder artifact metadata only, not real filesystem
  outputs.
- `audit` returns deterministic placeholder events only, not persisted audit
  logs.

## Phase 2.8 Error Contract

Invalid request bodies currently return FastAPI/Pydantic `422` validation
errors.

Placeholder endpoints should not expose local paths, secrets, tokens, passwords,
or traceback details.

An empty path segment such as `/task//report` does not bind a `task_id`, so
FastAPI returns `404 Not Found` before calling the placeholder report endpoint.

This phase still does not implement real RNA-seq execution or persistence.

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
  "task_id": "task_demo",
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
  "task_id": "task_demo",
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

### GET `/task/{task_id}/report`

Returns a deterministic placeholder report for the requested task ID. This
endpoint is intended for Phase 2 API integration only and does not generate a
report file, read inputs, write artifacts, or run QC, differential expression,
or enrichment analysis.

Expected response example:

```json
{
  "task_id": "task_demo",
  "status": "report_placeholder_ready",
  "summary": "Placeholder report generated for API integration. No real RNA-seq analysis was performed.",
  "sections": [
    {
      "section_id": "report_1",
      "title": "Task Overview",
      "content": "This placeholder report summarizes the submitted task configuration."
    },
    {
      "section_id": "report_2",
      "title": "QC Summary",
      "content": "QC execution is not implemented yet. This section is reserved for future QC results."
    },
    {
      "section_id": "report_3",
      "title": "Analysis Summary",
      "content": "Differential expression execution is not implemented yet. This section is reserved for future RNA-seq results."
    },
    {
      "section_id": "report_4",
      "title": "Reliability Notes",
      "content": "No biological or statistical conclusion should be drawn from this placeholder report."
    }
  ],
  "artifacts": [],
  "limitations": [
    "This endpoint does not generate a real report file.",
    "No input files are read.",
    "No QC, DESeq2, edgeR, limma, or enrichment analysis is executed.",
    "No biological conclusion should be drawn from this response."
  ]
}
```

### GET `/task/{task_id}/artifacts`

Returns a deterministic placeholder artifact list for the requested task ID.
This endpoint is intended for Phase 2 API integration only and does not read,
write, generate, or serve real artifact files.

Expected response example:

```json
{
  "task_id": "task_demo",
  "status": "artifacts_placeholder_ready",
  "artifacts": [
    {
      "artifact_id": "artifact_1",
      "name": "qc_report_placeholder.md",
      "artifact_type": "qc_report",
      "path": null,
      "description": "Placeholder QC report artifact. No file is generated yet.",
      "available": false
    },
    {
      "artifact_id": "artifact_2",
      "name": "analysis_report_placeholder.md",
      "artifact_type": "analysis_report",
      "path": null,
      "description": "Placeholder analysis report artifact. No file is generated yet.",
      "available": false
    },
    {
      "artifact_id": "artifact_3",
      "name": "audit_log_placeholder.json",
      "artifact_type": "audit_log",
      "path": null,
      "description": "Placeholder audit log artifact. No file is generated yet.",
      "available": false
    }
  ],
  "limitations": [
    "This endpoint does not read or write real artifact files.",
    "Artifact paths are placeholders and are not downloadable yet.",
    "Real artifact generation will be implemented in a later phase."
  ]
}
```

### GET `/task/{task_id}/audit`

Returns a deterministic placeholder audit trail for the requested task ID. This
endpoint is intended for Phase 2 API integration only and does not read
persisted task history, log files, or durable audit storage.

Expected response example:

```json
{
  "task_id": "task_demo",
  "status": "audit_placeholder_ready",
  "events": [
    {
      "event_id": "audit_1",
      "event_type": "task_created",
      "message": "Placeholder task creation event.",
      "timestamp": "placeholder_timestamp",
      "actor": "system",
      "metadata": {}
    },
    {
      "event_id": "audit_2",
      "event_type": "plan_generated",
      "message": "Placeholder analysis plan generation event.",
      "timestamp": "placeholder_timestamp",
      "actor": "system",
      "metadata": {}
    },
    {
      "event_id": "audit_3",
      "event_type": "qc_checked",
      "message": "Placeholder QC checking event.",
      "timestamp": "placeholder_timestamp",
      "actor": "system",
      "metadata": {}
    },
    {
      "event_id": "audit_4",
      "event_type": "run_placeholder_executed",
      "message": "Placeholder task run event. No real RNA-seq analysis was performed.",
      "timestamp": "placeholder_timestamp",
      "actor": "system",
      "metadata": {}
    },
    {
      "event_id": "audit_5",
      "event_type": "report_placeholder_generated",
      "message": "Placeholder report generation event. No real report file was created.",
      "timestamp": "placeholder_timestamp",
      "actor": "system",
      "metadata": {}
    },
    {
      "event_id": "audit_6",
      "event_type": "artifacts_placeholder_listed",
      "message": "Placeholder artifact listing event. No real files were generated.",
      "timestamp": "placeholder_timestamp",
      "actor": "system",
      "metadata": {}
    }
  ],
  "limitations": [
    "This endpoint does not read persisted task history.",
    "Audit events are deterministic placeholders.",
    "No database or durable audit storage is implemented yet.",
    "Timestamps are placeholders and should not be treated as real execution times."
  ]
}
```

Current limitations:

- This endpoint does not read persisted task history.
- Audit events are deterministic placeholders.
- No database or durable audit storage is implemented yet.
- Timestamps are placeholders and should not be treated as real execution
  times.

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
cd "<repo-root>"
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
cd "<repo-root>"
Invoke-RestMethod http://127.0.0.1:8010/health
```

## Create a Task

```powershell
cd "<repo-root>"
$task = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/task/create `
  -ContentType "application/json" `
  -Body '{}'

$task
```

## Create an Analysis Plan

```powershell
cd "<repo-root>"
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
  -Uri http://127.0.0.1:8010/task/plan `
  -ContentType "application/json" `
  -Body $body
```

## Create a QC Plan

```powershell
cd "<repo-root>"
$body = @{
  task_id = "task_demo"
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
cd "<repo-root>"
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

## Get a Placeholder Report

```powershell
cd "<repo-root>"
Invoke-RestMethod http://127.0.0.1:8010/task/task_demo/report
```

## Get Placeholder Artifacts

```powershell
cd "<repo-root>"
Invoke-RestMethod http://127.0.0.1:8010/task/task_demo/artifacts
```

## Get a Placeholder Audit Trail

```powershell
cd "<repo-root>"
Invoke-RestMethod http://127.0.0.1:8010/task/task_demo/audit
```

## Check Task Status

```powershell
cd "<repo-root>"
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
- The report endpoint returns a placeholder response only.
- The report endpoint does not generate a real report file.
- The report endpoint does not read input files or write artifacts.
- The report endpoint does not run QC, DESeq2, edgeR, limma, or enrichment
  analysis.
- The report endpoint does not support biological or statistical conclusions.
- The artifacts endpoint returns placeholder artifact metadata only.
- The artifacts endpoint does not read or write real artifact files.
- The artifacts endpoint does not create files under artifacts, exports, or
  storage directories.
- Artifact paths are placeholders and are not downloadable yet.
- The audit endpoint returns deterministic placeholder events only.
- The audit endpoint does not read persisted task history or log files.
- The audit endpoint does not create files under logs, audit, storage,
  artifacts, or exports directories.
- No database or durable audit storage is implemented yet.
- Audit timestamps are placeholders and should not be treated as real execution
  times.
- No file upload API is implemented in this Phase 2 skeleton.
- No database, object storage, queue, authentication, or authorization is wired
  into the task API.
- The task API currently returns placeholder task status, analysis plans, QC
  plans, run results, report responses, artifact lists, and audit trails only.

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
- Coze can call `GET /task/{task_id}/report` to request a deterministic
  placeholder report response.
- Coze can call `GET /task/{task_id}/artifacts` to request a deterministic
  placeholder artifact list.
- Coze can call `GET /task/{task_id}/audit` to request a deterministic
  placeholder audit trail.
- Coze can call `GET /task/{task_id}/status` to poll task status.
- The current API is not yet connected to real Bulk RNA-seq analysis.
- Future Coze workflows should treat returned tasks as placeholders until
  analysis dispatch and artifact APIs are implemented.
