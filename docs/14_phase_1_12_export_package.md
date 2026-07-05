# Phase 1.12 Project Export Package

Phase 1.12 adds a project-level export package for archiving, reviewing, and
sharing an existing evidence package. It does not rerun analysis, change
statistical outputs, alter reliability grading, or grant stronger conclusion
permissions.

## Purpose

The export package is a zip archive of one project's existing
`artifacts/{project_id}` directory. It is intended for:

- local backup
- audit review
- transfer to collaborators
- reproducibility review
- evidence package archival

Export is a packaging step only. It is not a new analysis run.

## Output Location

Exports are written to:

```text
exports/{project_id}/{project_id}_evidence_package.zip
```

The export service also writes a sidecar metadata file:

```text
exports/{project_id}/EXPORT_MANIFEST.json
```

## Zip Contents

The zip archive includes the evidence package files under
`artifacts/{project_id}`, including:

```text
01_summary.md
02_qc_report.md
03_method_selection.md
04_main_results/
05_validation_results/
06_figures/
07_tables/
08_reproducible_code/
09_environment/
10_audit_log.json
11_reliability_report.md
12_interpretation_summary.md
manifest.json
EXPORT_MANIFEST.json
```

The export excludes `.git`, Python cache files, temporary files, other project
artifact directories, and the export zip itself.

## EXPORT_MANIFEST.json

The zip-level `EXPORT_MANIFEST.json` records:

- `project_id`
- `created_at`
- `source_artifact_dir`
- `export_package_path`
- `included_files`
- `excluded_files`
- `manifest_present`
- `reliability_grade`
- `strong_conclusion_allowed`
- `primary_method_status`
- `validation_consistency_score`
- `warnings`

Each included file entry contains:

```json
{
  "path": "01_summary.md",
  "sha256": "...",
  "size_bytes": 123
}
```

If a single file hash cannot be computed, the export continues and records a
warning rather than failing the entire package.

## API

Create or refresh an export package:

```text
POST /projects/{project_id}/export
```

Return existing export package metadata:

```text
GET /projects/{project_id}/export
```

Response fields include:

```json
{
  "project_id": "...",
  "status": "created",
  "export_package_path": "...",
  "export_package_sha256": "...",
  "size_bytes": 123456,
  "created_at": "...",
  "included_file_count": 42,
  "warnings": []
}
```

If no export has been created, `GET` returns `status=not_created`. If the
project has no artifact directory, `POST` returns a structured error.

## UI

The local `/ui` page includes an Export Package section after Artifact Review.
It can create the package and display:

- export status
- export package path
- zip SHA256
- zip size
- included file count
- warnings

## Coze Report Adapter

`GET /coze/projects/{project_id}/report` includes `export_metadata` when an
export package already exists. Existing report fields keep their original
meaning.

## Interpretation Boundary

Export does not change:

- reliability grade
- `strong_conclusion_allowed`
- QC status
- validation consistency
- method status
- result interpretation guardrails

An exported package may be reviewed or shared, but it does not by itself allow a
strong scientific conclusion.

## Out of Scope

Phase 1.12 does not add:

- new omics types
- FASTQ processing
- Coze file upload
- MinIO/S3
- Nextflow or Snakemake
- browser download streaming
- changes to DESeq2, edgeR, or limma-voom logic
