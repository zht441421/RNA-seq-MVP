# Phase 5.4 Task Input Registration

Phase 5.4 adds a safe task-scoped input registration foundation. It lets
clients associate existing files under `BIOINFO_INPUT_ROOT` with a task before
running the current minimal CPM/log2FC or DESeq2 workflows. It does not add new
bioinformatics methods, frontend code, real Coze calls, workflow engines,
Docker, database server dependencies, or arbitrary filesystem access.

## Endpoint

```text
POST /task/{task_id}/inputs/register
```

Request:

```json
{
  "input_role": "metadata",
  "source_relative_path": "deseq2_minimal/metadata.csv"
}
```

Response:

```json
{
  "task_id": "task_0001",
  "input_role": "metadata",
  "safe_relative_path": "deseq2_minimal/metadata.csv",
  "registered": true,
  "warnings": [],
  "next_required_inputs": ["count_matrix"],
  "file_size_bytes": 42,
  "checksum_sha256": "..."
}
```

Unknown tasks return deterministic `404`:

```json
{"detail": "Task not found."}
```

## Supported Input Roles

The only supported roles are:

- `metadata`
- `count_matrix`

Empty roles, arbitrary role names, path-like roles, and traversal-like roles are
rejected.

## Accepted File Extensions

Registered source files must use one of:

- `.csv`
- `.tsv`
- `.txt`

Files such as `.env`, `pyproject.toml`, Python source, and other unsupported
extensions are rejected.

## Register Flow

The register endpoint:

1. Confirms the task exists.
2. Validates `input_role`.
3. Validates `source_relative_path` as a safe relative path under
   `BIOINFO_INPUT_ROOT`.
4. Confirms the file exists.
5. Computes file size and SHA-256 checksum.
6. Persists task input metadata in the local SQLite task store.
7. Appends a lifecycle event with safe input metadata.

Public responses include safe relative paths only. Local absolute paths are not
returned.

## Upload Flow

`POST /task/{task_id}/inputs/upload` is not implemented in Phase 5.4. Uploads
remain future work so this phase does not add multipart dependencies or
task-scoped file writing behavior.

## Integration With `/task/run`

Existing `/task/run` behavior is preserved when explicit `metadata_file` and
`count_matrix_file` request fields are provided.

If both request fields are omitted and both task inputs have been registered,
`/task/run` uses the registered safe relative paths.

If only one task input is registered and `/task/run` omits explicit paths, the
backend returns:

```json
{"detail": "Both metadata and count matrix inputs are required."}
```

If no task inputs are registered and no explicit paths are provided, existing
dry-run placeholder behavior remains unchanged.

## Coze And Front-End Example

A client can register both files, then run without repeating paths:

```text
POST /task/task_0001/inputs/register
POST /task/task_0001/inputs/register
POST /task/run
GET  /task/task_0001/coze-summary
```

The Coze summary may include:

```json
{
  "registered_inputs": {
    "metadata": "deseq2_minimal/metadata.csv",
    "count_matrix": "deseq2_minimal/counts.csv"
  }
}
```

## Safety Restrictions

The endpoint rejects:

- `../metadata.csv`
- `..\metadata.csv`
- `C:\temp\metadata.csv`
- `D:\temp\metadata.csv`
- `/tmp/metadata.csv`
- `.env`
- `pyproject.toml`
- source code files
- unsupported extensions

Responses must not expose:

- `D:\`
- `C:\`
- `/home/`
- `/mnt/`
- `file://`
- traceback details
- tokens
- passwords
- secrets

## Current Limitations

- No multipart upload endpoint is implemented.
- No file contents are copied or overwritten by registration.
- No frontend code is added.
- No real Coze API call is added.
- No authentication or authorization layer is added.
- Role-specific content parsing is left to existing run-time validators and
  executors.
