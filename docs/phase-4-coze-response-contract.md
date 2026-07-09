# Phase 4 Coze Response Contract

This document defines a safe structured response contract for future Coze-facing
layers that summarize Bulk RNA-seq task results. It is a documentation-only
contract in Phase 4.8. No Coze API call is implemented.

Phase 5.3 introduces `GET /task/{task_id}/coze-summary` as the preferred
structured response source for Coze and front-end task summaries.

## Recommended Fields

A Coze response payload should include:

- `task_id`
- `analysis_method`
- `formal_de_method`
- `status`
- `summary_message`
- `result_files`
- `threshold_summary`
- `top_genes_by_padj`
- `top_genes_by_abs_log2fc`
- `contrast`
- `positive_log2fc_interpretation`
- `negative_log2fc_interpretation`
- `warnings`
- `limitations`
- `interpretation_boundary`
- `recommended_next_steps`

## DESeq2 Threshold Summary

For DESeq2 results, `threshold_summary` should record:

- `padj_threshold`
- `abs_log2fc_threshold`
- `genes_passing_default_reporting_filter`
- `genes_with_valid_padj`
- `genes_with_na_padj`

The default Phase 4.8 reporting thresholds are:

- `padj <= 0.05`
- `abs(log2FoldChange) >= 1.0`

## Safe Summary Message

`summary_message` should describe the result without overclaiming:

```text
DESeq2 completed and produced formal statistical results. Candidate genes were summarized using the configured adjusted p-value and log2 fold-change thresholds. Statistical significance does not automatically imply biological significance.
```

## Result Files

`result_files` should use safe relative artifact names or paths:

- `deseq2_results.csv`
- `deseq2_interpretation_summary.json`
- `deseq2_summary.json`
- `deseq2_run_manifest.json`
- `report.md`

When a response is based on the Phase 4.9 synthetic demo dataset, Coze-facing
summaries should cite the result only as pipeline validation. They should state
that the demo data is synthetic and not suitable for biological interpretation.

## Interpretation Boundary

The response should include:

```text
Statistical significance does not automatically imply biological significance.
```

It should also state log2FoldChange direction from the recorded contrast. When
available, Coze-facing payloads should include:

```json
{
  "contrast": {
    "contrast_column": "condition",
    "contrast_numerator": "treatment",
    "contrast_denominator": "control",
    "direction": "treatment_vs_control"
  },
  "positive_log2fc_interpretation": "Higher in treatment relative to control",
  "negative_log2fc_interpretation": "Lower in treatment relative to control"
}
```

If the contrast was inferred instead of explicitly requested, the payload should
retain that fact and Coze should phrase the direction as inferred.

## Warnings

The `warnings` field should preserve important interpretation caveats:

- Adjusted p-values control false discovery rate under the statistical model.
- Statistical significance is not the same as biological significance.
- NA pvalue or padj can occur due to filtering, low counts, outlier handling,
  or model limitations.
- No batch correction or complex design was performed in this phase.
- No GO/KEGG/GSEA enrichment was performed.

## Limitations

The `limitations` field should include:

- DESeq2 Phase 4.8 uses the minimal design formula `~ condition`.
- Exactly two conditions are supported.
- Phase 5.5 supports explicit contrast direction only for `condition`.
- No batch correction is performed.
- No complex design formula is implemented.
- No GO, KEGG, GSEA, pathway, or enrichment analysis is performed.
- No visualization generation is performed.
- No edgeR or limma analysis is performed.

## Recommended Next Steps

`recommended_next_steps` should include:

- Review the experimental design and metadata.
- Confirm DESeq2 contrast/reference levels before interpreting direction.
- Inspect genes with NA pvalue or padj.
- Validate candidate genes with biological context and independent evidence.
- Add batch/covariate modeling in a future phase when metadata supports it.

## What Coze Should Not Say

Coze-facing summaries should not:

- should not claim causal biology
- should not claim pathway enrichment
- should not claim clinical significance
- should not treat padj alone as final biological truth
- should not hide missing/NA values
- should not invent gene annotations
- should not claim GO, KEGG, or GSEA results
- should not infer treatment/control direction unless the contrast/reference is explicitly recorded
