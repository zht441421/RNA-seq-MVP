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
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## Test `/health`

```powershell
cd "D:\coze agent\bioinformatics-agent"
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Create a Task

```powershell
cd "D:\coze agent\bioinformatics-agent"
$task = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/task/create `
  -ContentType "application/json" `
  -Body '{}'

$task
```

## Check Task Status

```powershell
cd "D:\coze agent\bioinformatics-agent"
Invoke-RestMethod http://127.0.0.1:8000/task/$($task.task_id)/status
```

Or replace the task ID manually:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/task/task_xxx/status
```

## Current Limitations

- Tasks are stored only in memory.
- Task state is lost when the server restarts.
- No real RNA-seq analysis is executed.
- No file upload API is implemented in this Phase 2 skeleton.
- No database, object storage, queue, authentication, or authorization is wired
  into the task API.
- The task API currently returns placeholder status only.

## Next Planned API Extensions

Likely next API additions include:

- task request schema for analysis type and input metadata
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
- Coze can call `GET /task/{task_id}/status` to poll task status.
- The current API is not yet connected to real Bulk RNA-seq analysis.
- Future Coze workflows should treat returned tasks as placeholders until
  analysis dispatch and artifact APIs are implemented.
