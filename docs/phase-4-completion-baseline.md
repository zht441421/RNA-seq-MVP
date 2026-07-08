# Phase 4 Completion Baseline

Phase 4 is complete as a release-candidate capability baseline. This document
freezes what the current API and local execution paths support, what they do
not support, and which boundaries must remain visible to users.

## Phase 4 Status

Phase 4.1 through Phase 4.9 are completed:

- Phase 4.1 minimal real Bulk RNA-seq workflow
- Phase 4.2 RNA-seq input content validation
- Phase 4.3 report boundaries
- Phase 4.4 minimal RNA-seq demo data and e2e validation
- Phase 4.5 formal DE method contract
- Phase 4.6 DESeq2 preflight checks
- Phase 4.7 minimal real DESeq2 execution chain
- Phase 4.8 DESeq2 interpretation contract
- Phase 4.9 DESeq2 demo e2e validation

Latest baseline tag before Phase 4.10:

```text
phase-4-9-deseq2-demo-e2e
```

## Current Supported Workflows

The current supported workflows are:

- `minimal_cpm_log2fc`
- `deseq2` when preflight is ready

The default `POST /task/run` behavior remains `minimal_cpm_log2fc` unless a
formal DESeq2 request is made explicitly.

## Current API Endpoints

The Phase 4 baseline includes these public endpoints:

- `GET /health`
- `POST /task/create`
- `GET /task/{task_id}/status`
- `POST /task/plan`
- `POST /task/qc`
- `POST /task/run`
- `POST /task/validate-inputs`
- `GET /task/{task_id}/report`
- `GET /task/{task_id}/artifacts`
- `GET /task/{task_id}/audit`
- `GET /task/formal-de/preflight`

No public API schema change is introduced by the Phase 4.10 completion
baseline.

## Minimal RNA-seq Workflow Outputs

The `minimal_cpm_log2fc` workflow writes these task-scoped artifacts:

- `run_manifest.json`
- `execution_summary.json`
- `qc_summary.json`
- `normalized_counts_cpm.csv`
- `differential_expression_results.csv`
- `report.md`

The minimal method is exploratory. It computes QC metrics, CPM-normalized
counts, and a preliminary log2 fold-change ranking. It does not perform a
formal statistical test, and it does not produce `pvalue` or `padj` values.
There are no fake p-values in the minimal workflow.

## DESeq2 Workflow Outputs

The `deseq2` workflow writes these task-scoped artifacts after a successful
preflight-gated run:

- `deseq2_results.csv`
- `deseq2_summary.json`
- `deseq2_run_manifest.json`
- `deseq2_interpretation_summary.json`
- `report.md`

`pvalue` and `padj` are available only for successful DESeq2 runs. DESeq2
requires `GET /task/formal-de/preflight` to report readiness before execution.
The service does not attempt automatic package installation.

## Demo Data And Scripts

Current demo data and validation scripts:

- `data/demo/rnaseq_minimal/`
- `scripts/run_phase_4_4_demo.py`
- `data/demo/deseq2_minimal/`
- `scripts/run_phase_4_9_deseq2_demo.py`

Demo data are synthetic. Demo results are for pipeline validation only and are
not for biological interpretation.

## Safety And Reproducibility Boundaries

The Phase 4 baseline keeps these boundaries:

- no absolute local paths in public responses
- sanitized errors
- no fake p-values
- no fake `padj` values
- no automatic package installation
- no traceback exposure
- no tokens, passwords, or secrets exposure
- task-scoped output directories
- deterministic tests

## Current Unsupported Features

The Phase 4 baseline does not support:

- edgeR
- limma
- batch correction
- complex design formulas
- GO enrichment
- KEGG enrichment
- GSEA
- pathway analysis
- visualization generation
- database persistence
- real Coze API integration
- multi-omics integration

## Phase 5 Recommended Direction

Phase 5 should focus on one carefully bounded product or platform step, such
as:

- persistent task storage
- real file upload/download integration
- Coze-facing response API
- DESeq2 contrast/reference control
- frontend/report download contract
