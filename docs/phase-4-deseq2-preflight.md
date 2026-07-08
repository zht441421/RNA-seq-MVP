# Phase 4.6 DESeq2 Preflight

Phase 4.6 adds a safe local environment preflight for future DESeq2 support.
It checks whether the runtime appears ready to execute DESeq2 in a later phase,
but it does not run differential expression analysis.

## Purpose

The preflight answers one narrow question:

```text
Can this local environment support future DESeq2 execution?
```

It is separate from `POST /task/run` and does not require a `task_id`. It does
not mutate the in-memory task registry and does not create artifacts.

## Checks Performed

The preflight checks:

- Whether `R` is available.
- Whether `Rscript` is available.
- The R version, when it can be read safely.
- The Rscript version, when it can be read safely.
- Whether the `BiocManager` R package is installed.
- Whether the `DESeq2` R package is installed.
- Whether all required components are present.

The service may call:

```powershell
R --version
Rscript --version
Rscript --vanilla -e "requireNamespace(...)"
```

Package checks use `requireNamespace(..., quietly = TRUE)` only.

## What Is Not Performed

- No real DESeq2 differential expression analysis is run.
- No count matrix or metadata file is analyzed.
- No p-values, adjusted p-values, q-values, or statistical significance labels
  are produced.
- No edgeR, limma, enrichment, pathway, GSEA, GO, or KEGG analysis is run.
- No Docker, Snakemake, Nextflow, Coze call, or database persistence is added.
- No task artifacts are created.

## No Package Installation

The preflight never installs or updates R packages. It does not call
`BiocManager::install`, and it does not modify the user's R environment.

## Endpoint

```powershell
GET /task/formal-de/preflight
```

The response includes:

- `status: "formal_de_preflight_completed"`
- `formal_method: "deseq2"`
- `ready`
- `checks`
- `warnings`
- `errors`
- `limitations`

Example unavailable response:

```json
{
  "status": "formal_de_preflight_completed",
  "formal_method": "deseq2",
  "ready": false,
  "checks": {
    "r_available": false,
    "rscript_available": false,
    "r_version": null,
    "rscript_version": null,
    "biocmanager_available": false,
    "deseq2_available": false,
    "checked_at": "2026-07-09T00:00:00Z",
    "commands_checked": []
  },
  "warnings": [],
  "errors": [
    "R executable is not available.",
    "Rscript executable is not available."
  ],
  "limitations": [
    "This preflight only checks local environment readiness for future DESeq2 execution.",
    "No DESeq2 differential expression analysis is run.",
    "No p-values, adjusted p-values, q-values, or statistical significance labels are produced.",
    "No R or Bioconductor packages are installed, updated, or modified.",
    "DESeq2 execution is not available until R, Rscript, BiocManager, and DESeq2 are installed."
  ]
}
```

Missing R, Rscript, BiocManager, or DESeq2 returns HTTP 200 with
`ready: false`. The endpoint should not expose local absolute paths,
tracebacks, credentials, or internal stack details.

## Service Check

The service entry point is:

```python
from backend.app.services.formal_de_preflight import run_deseq2_preflight

result = run_deseq2_preflight()
```

The service returns deterministic public fields suitable for tests and endpoint
serialization. Command execution uses list arguments, no shell execution, short
timeouts, and sanitized output.

## Next Step

Phase 4.7 may add a minimal DESeq2 execution chain after the environment
preflight contract is stable. Until then, `deseq2` remains a planned formal
method and is not available through `POST /task/run`.
