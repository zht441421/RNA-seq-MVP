# Phase 4 Formal Differential Expression Contract

Phase 4.5 defines the method contract that separates the current minimal
Bulk RNA-seq MVP workflow from future formal differential expression methods.
It does not implement DESeq2, edgeR, limma, Rscript, containers, workflow
engines, enrichment analysis, or external tool calls.

Phase 4.6 adds a read-only DESeq2 environment preflight endpoint. The preflight
checks whether R, Rscript, BiocManager, and DESeq2 are available for future
DESeq2 execution. It does not run differential expression analysis.

Phase 4.7 adds minimal real DESeq2 execution when `deseq2` is explicitly
requested and the preflight is ready. edgeR and limma remain planned but not
implemented.

## Current Methods

The default current execution method is:

```text
minimal_cpm_log2fc
```

Display name:

```text
Minimal CPM + preliminary log2 fold-change ranking
```

This method reads validated metadata and count matrix files, computes library
sizes, computes CPM-normalized counts, filters low-expression genes, and writes
a preliminary group-level log2 fold-change ranking for exactly two condition
groups.

The gated formal method is:

```text
deseq2
```

DESeq2 is available only when explicitly requested through `analysis_method` or
`formal_de_method` and the Phase 4.6 preflight returns `ready: true`.

## Formal Method Status

The formal differential expression method status is:

- `deseq2`: minimally implemented when preflight is ready.
- `edger`: not implemented.
- `limma`: not implemented.

edgeR and limma are reserved for future phases.

## Phase 4.6 DESeq2 Preflight

`GET /task/formal-de/preflight` returns safe environment readiness metadata for
the planned `deseq2` method. It does not require a task ID, does not mutate the
task registry, and does not create artifacts.

The preflight reports whether these components are available:

- `R`
- `Rscript`
- `BiocManager`
- `DESeq2`

It may report R and Rscript versions when available. Missing components return
HTTP 200 with `ready: false` and deterministic limitations.

`formal_de_ready` in the current method contract remains about method contract
readiness in generated minimal workflow outputs. It does not mean that formal
DESeq2 result fields are available. Phase 4.6 readiness metadata only indicates
whether the local environment appears prepared for future DESeq2 execution.

In Phase 4.7 DESeq2 output summaries, `formal_de_ready: true` means the DESeq2
execution path passed preflight and produced formal DESeq2 outputs for that
task. It does not imply enrichment analysis, complex design support, or any
result interpretation beyond the generated DESeq2 table.

## Output Method Metadata

`execution_summary.json` records:

- `analysis_method`
- `analysis_method_display_name`
- `formal_de_method`
- `formal_de_ready`
- `statistical_test_performed`
- `pvalue_available`
- `adjusted_pvalue_available`
- `external_tools_called`
- `method_limitations`
- `next_supported_formal_methods`

For the current minimal method, formal DE readiness and all statistical result
availability flags are `false`.

`deseq2_summary.json` records:

- `analysis_method`
- `formal_de_method`
- `formal_de_ready`
- `statistical_test_performed`
- `pvalue_available`
- `adjusted_pvalue_available`
- `external_tools_called`
- `external_tool`
- `r_package`
- `design_formula`
- `input_sample_count`
- `input_gene_count`
- `result_gene_count`
- `pvalue_column`
- `adjusted_pvalue_column`
- `limitations`
- `warnings`

`run_manifest.json` records:

- `analysis_method`
- `execution_mode`
- `formal_de_ready`
- `requested_formal_method`
- `supported_future_formal_methods`

`differential_expression_results.csv` remains a preliminary ranking artifact.
It may include safe method metadata fields such as:

- `analysis_method`
- `formal_statistical_test`
- `pvalue_available`
- `adjusted_pvalue_available`

It must not include real statistical result fields such as `pvalue`, `padj`,
`qvalue`, significance labels, false discovery rate values, enrichment outputs,
or pathway outputs.

`deseq2_results.csv` is the Phase 4.7 formal DESeq2 result table and may
include:

- `gene_id`
- `baseMean`
- `log2FoldChange`
- `lfcSE`
- `stat`
- `pvalue`
- `padj`

## Not Implemented Behavior

If a request asks for `edger` or `limma` through either
`analysis_method` or `formal_de_method`, the API returns:

```text
FORMAL_DE_METHOD_NOT_IMPLEMENTED
```

The response uses a deterministic public error payload, does not expose local
paths or internal stack details, does not create analysis output files, and does
not mark the task as `minimal_analysis_completed`.

If a request asks for `deseq2` but the preflight is not ready, the API returns:

```text
DESEQ2_PREFLIGHT_NOT_READY
```

No DESeq2 analysis Rscript is run and no fake DESeq2 output is generated.

Unsupported arbitrary method names return a safe unsupported-method error and
do not echo untrusted method text back to the client.

## Current Limitations

- The minimal default method fits no formal statistical model.
- The minimal default method produces no p-values, adjusted p-values, q-values,
  or false discovery rate estimates.
- DESeq2 is invoked only for explicit `deseq2` requests after preflight is ready.
- edgeR and limma runtimes are not invoked.
- No Docker, Snakemake, Nextflow, Coze call, or workflow engine is invoked.
- No GSEA, GO, KEGG, pathway, or enrichment analysis is performed.
- The preliminary ranking is exploratory only and must not be treated as a
  final DEG list.
- DESeq2 Phase 4.7 uses only the minimal design formula `~ condition`; no batch
  correction or complex design is implemented yet.

## Expected Future Fields

Future formal DE phases may extend method-specific fields after additional
formal execution support exists, such as:

- `formal_de_method`
- `design_formula`
- `contrast`
- `pvalue`
- `adjusted_pvalue`
- `base_mean` or method-specific abundance summaries
- `test_statistic`
- `standard_error`
- method version and runtime metadata

Those fields remain intentionally absent from the default minimal
`minimal_cpm_log2fc` contract unless a formal method produces them.
