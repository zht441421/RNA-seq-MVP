# Phase 5.2 Artifact Download Contract

Phase 5.2 adds a safe download contract for generated task artifacts. It does
not change minimal CPM/log2FC execution, DESeq2 execution, input upload
behavior, frontend code, Coze integration, or workflow dependencies.

## Endpoint

```text
GET /task/{task_id}/artifacts/{artifact_name}/download
```

The endpoint returns the file content for a known task-scoped artifact when the
artifact metadata and resolved filesystem path both pass safety checks.

## Purpose

Clients can download generated artifacts without learning local absolute paths
or gaining arbitrary filesystem read access. The route is intended to sit behind
future Coze or frontend download links while preserving the existing artifact
metadata response shape.

## Safe Download Rules

- `task_id` must identify an existing task.
- `artifact_name` must be a single safe filename.
- The artifact must be registered in persisted artifact metadata or be part of
  the current planned task artifact contract.
- Registered `safe_relative_path` values must match
  `tasks/{task_id}/{artifact_name}`.
- The final resolved path must remain under the configured output root and the
  task output directory.
- The file must exist before content is returned.
- The download filename is `artifact_name` only.
- Public errors are deterministic and do not expose local absolute paths,
  tracebacks, tokens, passwords, or secrets.

## Allowed Artifact Examples

Minimal workflow examples:

```text
run_manifest.json
execution_summary.json
qc_summary.json
normalized_counts_cpm.csv
differential_expression_results.csv
report.md
```

DESeq2 workflow examples:

```text
deseq2_results.csv
deseq2_summary.json
deseq2_run_manifest.json
deseq2_interpretation_summary.json
report.md
```

Dry-run examples:

```text
run_manifest.json
execution_summary.json
planned_steps.json
```

## Forbidden Path Patterns

The download contract rejects path traversal, absolute paths, nested paths, and
non-artifact local files. Examples:

```text
../report.md
..\report.md
tasks/task_0001/report.md
/tmp/report.md
C:\temp\report.md
D:\temp\report.md
.env
tasks.sqlite3
source.py
```

## Missing Artifact Behavior

Unknown tasks and unknown artifacts return:

```json
{"detail": "Artifact not found."}
```

Registered or planned artifacts whose files are missing also return the same
deterministic `404` response. This avoids revealing whether a local path exists
outside the task artifact contract.

## Content Types

The current response media type mapping is:

```text
.json -> application/json
.csv  -> text/csv
.md   -> text/markdown
.txt  -> text/plain
other allowed safe suffixes -> application/octet-stream
```

## Security Boundaries

This phase does not expose arbitrary filesystem reads. It never returns local
absolute paths as the download filename or in structured error bodies. The
resolver checks both stored artifact metadata and the final resolved filesystem
path before `FileResponse` is used.

## Current Limitations

- No file upload endpoints are added.
- No frontend download UI is added.
- No Coze API calls or external storage links are added.
- No Docker, Snakemake, Nextflow, or database server dependency is added.
- No new bioinformatics methods are added.
- The endpoint has no authentication or authorization layer yet.

## Future Integration

Future Coze or frontend integrations can call this endpoint after listing task
artifacts from:

```text
GET /task/{task_id}/artifacts
```

Download links should pass only the public `name` field as `artifact_name`, not
the metadata `path` value and never a local absolute path.
