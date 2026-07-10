# Phase 5.5 DESeq2 Contrast Control

Phase 5.5 adds explicit contrast/reference direction control for the current
two-group Bulk RNA-seq workflows. It does not add edgeR, limma, enrichment
analysis, frontend code, real Coze API calls, Docker, Snakemake, Nextflow,
database server dependencies, workflow engines, arbitrary filesystem reads, or
local absolute path exposure.

Phase 5.6 demonstrates explicit contrast behavior in the R-independent minimal
workflow through `scripts/run_phase_5_6_coze_ready_demo.py`.

## Purpose

The goal is to make log2 fold-change direction explicit:

```text
experimental condition vs reference condition
```

Examples:

- `treatment` vs `control`
- `disease` vs `normal`
- `case` vs `control`

## Request Fields

`POST /task/run` accepts these optional fields:

```json
{
  "contrast_column": "condition",
  "contrast_numerator": "treatment",
  "contrast_denominator": "control"
}
```

Current MVP support is limited to `contrast_column: "condition"`.

## Default Inferred Behavior

If no contrast fields are provided, existing behavior is preserved. For
two-group metadata, the service uses the deterministic first-seen condition
order:

- denominator: first condition encountered in metadata
- numerator: second condition encountered in metadata

Outputs include `contrast_source: "inferred"` so consumers can see that the
direction was not explicitly supplied.

## Explicit Behavior

If an explicit contrast is provided:

- `contrast_numerator` and `contrast_denominator` must both be present.
- Numerator and denominator must be different.
- Both values must exist in the metadata `condition` column.
- The metadata must contain exactly two condition groups.
- Unsupported `contrast_column` values are rejected deterministically.

The shared contrast payload is:

```json
{
  "contrast": {
    "contrast_column": "condition",
    "contrast_numerator": "treatment",
    "contrast_denominator": "control",
    "direction": "treatment_vs_control",
    "positive_log2fc_interpretation": "Higher in treatment relative to control",
    "negative_log2fc_interpretation": "Lower in treatment relative to control",
    "contrast_source": "explicit",
    "inferred": false
  }
}
```

## Minimal Workflow Behavior

For `minimal_cpm_log2fc`, log2 fold change means:

```text
log2(mean CPM of contrast_numerator + 1) - log2(mean CPM of contrast_denominator + 1)
```

The output table keeps existing compatibility columns such as
`mean_cpm_group_1`, `mean_cpm_group_2`, and `log2_fold_change`. In Phase 5.5,
`group_1` is the denominator and `group_2` is the numerator. Additional contrast
columns identify the direction.

## DESeq2 Behavior

For `deseq2`, the generated R script calls DESeq2 with an explicit contrast:

```r
results(dds, contrast = c(contrast_column, contrast_numerator, contrast_denominator))
```

The design remains the current MVP formula:

```text
~ condition
```

Positive `log2FoldChange` means higher expression in
`contrast_numerator` relative to `contrast_denominator`. Negative
`log2FoldChange` means lower expression in `contrast_numerator` relative to
`contrast_denominator`.

## Validation Errors

The validator rejects:

- missing `contrast_column` in metadata
- missing numerator value in metadata
- missing denominator value in metadata
- numerator equal to denominator
- only one of numerator or denominator provided
- unsupported `contrast_column`
- more than two condition groups
- malformed or empty contrast values

Errors are deterministic and safe. They do not expose local absolute paths,
tracebacks, internal R commands, tokens, passwords, or secrets.

## Output Artifacts

Minimal workflow artifacts with contrast metadata:

- `execution_summary.json`
- `run_manifest.json`
- `differential_expression_results.csv`
- `report.md`

DESeq2 workflow artifacts with contrast metadata:

- `deseq2_summary.json`
- `deseq2_run_manifest.json`
- `deseq2_interpretation_summary.json`
- `report.md`

## Coze Summary

`GET /task/{task_id}/coze-summary` includes:

- `contrast`
- `positive_log2fc_interpretation`
- `negative_log2fc_interpretation`

Coze-facing summaries should present log2FC direction from these fields and
should not infer treatment/control meaning when contrast metadata is missing.

## Limitations

- Exactly two condition groups are supported.
- Only `condition` is supported as the contrast column.
- No batch correction or complex design formula is implemented.
- No edgeR or limma execution is added.
- No GO, KEGG, GSEA, pathway, or enrichment analysis is added.
- Minimal CPM/log2FC results remain exploratory and are not formal differential
  expression statistics.
