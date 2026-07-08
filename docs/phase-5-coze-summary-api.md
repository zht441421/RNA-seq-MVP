# Phase 5.3 Coze Summary API

Phase 5.3 adds a safe structured task result summary endpoint for Coze and
front-end consumers. It does not change minimal CPM/log2FC execution, DESeq2
execution, file upload behavior, frontend code, Coze API calls, workflow
engines, Docker, or database server dependencies.

## Endpoint

```text
GET /task/{task_id}/coze-summary
```

Unknown tasks return deterministic `404`:

```json
{"detail": "Task not found."}
```

Existing tasks return `200`, including partial summaries when result artifacts
are incomplete or not yet available.

## Purpose

The endpoint gives Coze and future UI code a compact JSON source for safe result
presentation. It avoids raw large CSV content, local absolute paths, tracebacks,
secrets, and arbitrary filesystem reads.

## Response Fields

The response includes:

- `task_id`
- `status`
- `analysis_method`
- `formal_de_method`
- `statistical_test_performed`
- `pvalue_available`
- `adjusted_pvalue_available`
- `summary_message`
- `result_files`
- `download_links`
- `threshold_summary`
- `top_genes_by_padj`
- `top_genes_by_abs_log2fc`
- `warnings`
- `limitations`
- `interpretation_boundary`
- `recommended_next_steps`
- `safe_to_present`

## Minimal Workflow Behavior

For tasks that appear to use `minimal_cpm_log2fc`, the summary reports:

```text
analysis_method: minimal_cpm_log2fc
formal_de_method: null
statistical_test_performed: false
pvalue_available: false
adjusted_pvalue_available: false
```

The summary message states that CPM/log2FC output is exploratory ranking only,
not formal differential expression statistics. Warnings and limitations include:

- no p-values
- no adjusted p-values
- no formal statistical test
- no batch correction
- no GO/KEGG/GSEA enrichment

## DESeq2 Workflow Behavior

When `deseq2_interpretation_summary.json` is registered and readable, the
endpoint uses it to populate:

- `threshold_summary`
- `top_genes_by_padj`
- `top_genes_by_abs_log2fc`
- `warnings`
- `limitations`
- `interpretation_boundary`

DESeq2 summaries report:

```text
analysis_method: deseq2
formal_de_method: deseq2
statistical_test_performed: true
pvalue_available: true
adjusted_pvalue_available: true
```

The response preserves key interpretation boundaries:

- statistical significance is not biological significance
- log2FoldChange direction depends on DESeq2 contrast/reference level
- NA pvalue or padj can occur because of filtering, low counts, outlier
  handling, or model limitations
- no GO/KEGG/GSEA enrichment was performed
- no batch correction or complex design was performed

## Download Links

Each `result_files` entry includes:

- `artifact_name`
- `artifact_type`
- `description`
- `download_url`
- `available`

`download_url` is a relative API path only, for example:

```text
/task/task_0001/artifacts/report.md/download
```

The summary never includes local absolute paths such as `D:\...`, `C:\...`,
`/home/...`, `/mnt/...`, or `file://...`.

## Partial Summary Behavior

If a task exists but result artifacts are missing, the endpoint returns `200`
with a partial summary, warnings, and limitations. If the DESeq2 interpretation
artifact is malformed JSON, the endpoint returns a partial DESeq2 summary with:

```text
Some result artifacts could not be parsed safely.
```

Raw parser exceptions and local paths are not exposed.

## Safety Boundaries

- No arbitrary filesystem read access is exposed.
- Only registered or planned task-scoped artifacts may be read.
- The endpoint reads only safe JSON summary artifacts, not large CSV result
  contents.
- Local absolute paths, tracebacks, tokens, passwords, and secrets are
  sanitized from the final payload.
- Download links point to the existing safe artifact download endpoint.

## What Coze Should Not Claim

Coze-facing responses should not claim:

- causal biology
- pathway enrichment
- clinical significance
- treatment/control direction unless contrast/reference levels are explicit
- final DEG lists from minimal CPM/log2FC output
- biological significance from padj or log2FoldChange alone
- GO, KEGG, or GSEA results

## Current Limitations

- No authentication or authorization layer is added.
- No file upload endpoint is added.
- No frontend code is added.
- No real Coze API call is added.
- No new analysis method or workflow engine is added.
- Summary quality depends on available task and artifact metadata.
