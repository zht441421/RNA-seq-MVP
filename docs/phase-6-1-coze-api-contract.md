# Phase 6.1 Coze API Contract

Phase 6.1 documents how a future Coze plugin or workflow should call the
existing task lifecycle API. It does not call real Coze APIs, add frontend code,
add routes, regenerate OpenAPI, or change analysis behavior.

## Recommended Coze-Facing Endpoint Sequence

1. `POST /task/create`
2. `POST /task/{task_id}/inputs/register`
3. `POST /task/run`
4. `GET /task/{task_id}/status`
5. `GET /task/{task_id}/coze-summary`
6. `GET /task/{task_id}/artifacts/{artifact_name}/download`

Optional preparation calls such as `POST /task/plan`, `POST /task/qc`, and
`GET /task/formal-de/preflight` remain useful for local validation and DESeq2
readiness checks.

## Request Examples

Create a task:

```http
POST /task/create
```

```json
{
  "task_type": "bulk_rnaseq",
  "parameters": {
    "client": "coze_contract_example"
  }
}
```

Register metadata:

```http
POST /task/task_0001/inputs/register
```

```json
{
  "input_role": "metadata",
  "source_relative_path": "rnaseq_minimal/metadata.csv"
}
```

Register count matrix:

```json
{
  "input_role": "count_matrix",
  "source_relative_path": "rnaseq_minimal/counts.csv"
}
```

Run the minimal workflow with an explicit contrast:

```json
{
  "task_id": "task_0001",
  "project_name": "coze_contract_demo",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "analysis_goal": ["qc", "differential_expression"],
  "group_column": "condition",
  "contrast": "treatment_vs_control",
  "execution_mode": "minimal_real",
  "analysis_method": "minimal_cpm_log2fc",
  "contrast_column": "condition",
  "contrast_numerator": "treatment",
  "contrast_denominator": "control"
}
```

Run DESeq2 only after preflight readiness:

```json
{
  "task_id": "task_0001",
  "project_name": "coze_contract_demo",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "analysis_goal": ["qc", "differential_expression"],
  "group_column": "condition",
  "contrast": "treatment_vs_control",
  "execution_mode": "formal_de_real",
  "analysis_method": "deseq2",
  "formal_de_method": "deseq2",
  "contrast_column": "condition",
  "contrast_numerator": "treatment",
  "contrast_denominator": "control"
}
```

DESeq2 requires `GET /task/formal-de/preflight` to report ready. If the preflight
check is not ready, the backend returns the existing DESeq2 not-ready error and
does not run Rscript.

## Response Examples

Task creation:

```json
{
  "task_id": "task_0001",
  "status": "created",
  "message": "Task created."
}
```

Registered input:

```json
{
  "task_id": "task_0001",
  "input_role": "metadata",
  "safe_relative_path": "rnaseq_minimal/metadata.csv",
  "registered": true,
  "warnings": [],
  "next_required_inputs": ["count_matrix"],
  "file_size_bytes": 128,
  "checksum_sha256": "example-sha256-placeholder"
}
```

Minimal run:

```json
{
  "task_id": "task_0001",
  "project_name": "coze_contract_demo",
  "status": "minimal_analysis_completed",
  "run_steps": [
    {
      "step_id": "run_1",
      "name": "Validate and load inputs",
      "status": "completed",
      "message": "Input paths were validated and tabular files were parsed."
    }
  ],
  "artifacts": [
    {
      "name": "report.md",
      "artifact_type": "minimal_analysis_report",
      "path": "tasks/task_0001/report.md",
      "available": true,
      "description": "Generated report describing the minimal Bulk RNA-seq MVP analysis and limitations."
    }
  ],
  "limitations": [
    "The minimal workflow is exploratory and does not produce p-values."
  ]
}
```

Coze summary:

```json
{
  "task_id": "task_0001",
  "status": "run_placeholder_ready",
  "analysis_method": "minimal_cpm_log2fc",
  "statistical_test_performed": false,
  "pvalue_available": false,
  "adjusted_pvalue_available": false,
  "summary_message": "Minimal CPM/log2FC output is exploratory ranking only.",
  "download_links": {
    "report.md": "/task/task_0001/artifacts/report.md/download"
  },
  "contrast": {
    "contrast_column": "condition",
    "contrast_numerator": "treatment",
    "contrast_denominator": "control",
    "direction": "treatment_vs_control"
  },
  "safe_to_present": true
}
```

## Minimal Workflow Example

For `minimal_cpm_log2fc`, Coze may call task creation, input registration,
`POST /task/plan`, `POST /task/qc`, `POST /task/run`, status polling, summary
fetching, and artifact download. The summary may mention basic QC metrics,
CPM-normalized output, and preliminary log2FC ranking.

Coze must state that the minimal workflow does not perform a formal
differential expression statistical test and does not provide p-values or
adjusted p-values.

## DESeq2 Workflow Example With Preflight Caveat

For `deseq2`, Coze should first check:

```text
GET /task/formal-de/preflight
```

Only when `ready` is true should Coze submit a `POST /task/run` payload with
`execution_mode: "formal_de_real"` and `analysis_method: "deseq2"`. If preflight
is not ready, Coze may explain that local R, Rscript, BiocManager, or DESeq2 is
not available and should not claim that DESeq2 ran.

## Explicit Contrast Example

Use explicit contrast fields whenever the user has confirmed the condition
direction:

```json
{
  "contrast_column": "condition",
  "contrast_numerator": "treatment",
  "contrast_denominator": "control"
}
```

With this contrast, positive log2FC means higher expression in `treatment`
relative to `control`. Negative log2FC means lower expression in `treatment`
relative to `control`.

## Error Examples

Unknown task:

```json
{
  "detail": "Task not found: task_missing"
}
```

Missing input:

```json
{
  "detail": "Both metadata and count matrix inputs are required."
}
```

Invalid contrast:

```json
{
  "detail": {
    "error_code": "CONTRAST_VALIDATION_FAILED",
    "message": "Contrast validation failed.",
    "errors": [
      "contrast_numerator 'case' is not present in metadata."
    ]
  }
}
```

Artifact not found:

```json
{
  "detail": "Artifact not found."
}
```

DESeq2 preflight not ready:

```json
{
  "detail": {
    "error_code": "DESEQ2_PREFLIGHT_NOT_READY",
    "message": "DESeq2 execution is not available because the preflight check is not ready.",
    "formal_method": "deseq2",
    "errors": [
      "DESeq2 execution is not available because the preflight check is not ready."
    ],
    "warnings": [],
    "preflight": {
      "ready": false,
      "formal_method": "deseq2",
      "checks": {
        "r_available": false,
        "rscript_available": false,
        "biocmanager_available": false,
        "deseq2_available": false
      },
      "limitations": [
        "DESeq2 execution is not available until R, Rscript, BiocManager, and DESeq2 are installed."
      ]
    }
  }
}
```

## What Coze May Safely Say

Coze may safely say:

- a task was created
- metadata or count matrix input was registered with a safe relative path
- the minimal workflow completed, if the run response says so
- DESeq2 completed, if the run response says so and artifacts are present
- artifact download links are available through relative API paths
- minimal workflow output is exploratory CPM/log2FC ranking
- DESeq2 output includes p-value and adjusted p-value columns only when DESeq2
  actually ran
- limitations and warnings should be reviewed with the result

## What Coze Must Not Claim

Coze must not claim:

- biological significance without user validation
- enrichment if not run
- p-values for minimal workflow
- DESeq2 if preflight not ready
- edgeR, limma, GO, KEGG, or GSEA results in this phase
- clinical, causal, or pathway-level conclusions from these outputs alone

## Download URL Behavior

Download URLs in Coze-facing payloads are relative API paths only:

```text
/task/task_0001/artifacts/report.md/download
```

They must not contain a local absolute path, `file://` URL, or filesystem root.
A future public deployment adapter may combine the relative path with a public
API base URL outside the backend response.

## Example Files

Machine-readable examples live under:

```text
docs/examples/coze/
```

They are intentionally small, deterministic, and safe: no local absolute paths,
no real credentials, no private data, and no huge payloads.
