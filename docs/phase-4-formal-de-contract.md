# Phase 4 Formal Differential Expression Contract

Phase 4.5 defines the method contract that separates the current minimal
Bulk RNA-seq MVP workflow from future formal differential expression methods.
It does not implement DESeq2, edgeR, limma, Rscript, containers, workflow
engines, enrichment analysis, or external tool calls.

## Current Method

The only current execution method is:

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

## Future Formal Methods

The planned formal differential expression methods are:

- `deseq2`
- `edger`
- `limma`

These names are reserved for future phases. They are not executed in Phase 4.5.

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
or pathway outputs until a formal method is implemented.

## Not Implemented Behavior

If a request asks for `deseq2`, `edger`, or `limma` through either
`analysis_method` or `formal_de_method`, the API returns:

```text
FORMAL_DE_METHOD_NOT_IMPLEMENTED
```

The response uses a deterministic public error payload, does not expose local
paths or internal stack details, does not create analysis output files, and does
not mark the task as `minimal_analysis_completed`.

Unsupported arbitrary method names return a safe unsupported-method error and
do not echo untrusted method text back to the client.

## Current Limitations

- No formal statistical model is fitted.
- No p-values, adjusted p-values, q-values, or false discovery rate estimates
  are produced.
- No DESeq2, edgeR, or limma runtime is invoked.
- No Rscript, Docker, Snakemake, Nextflow, Coze call, or external command is
  invoked.
- No GSEA, GO, KEGG, pathway, or enrichment analysis is performed.
- The preliminary ranking is exploratory only and must not be treated as a
  final DEG list.

## Expected Future Fields

Future formal DE phases may add method-specific fields only after real formal
execution exists, such as:

- `formal_de_method`
- `design_formula`
- `contrast`
- `pvalue`
- `adjusted_pvalue`
- `base_mean` or method-specific abundance summaries
- `test_statistic`
- `standard_error`
- method version and runtime metadata

Those fields are intentionally absent from the current minimal contract.
