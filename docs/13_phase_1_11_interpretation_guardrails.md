# Phase 1.11 Result Table Interpretation Guardrails

Phase 1.11 adds a guarded interpretation layer for real and mock Bulk RNA-seq
result tables. It does not change DESeq2, edgeR, limma-voom, Docker, input
schemas, omics scope, or the core reliability grading rules.

## Boundary

The interpretation layer summarizes statistical differential expression result
tables. It may report:

- total DESeq2 result rows
- FDR/log2FC significant row counts
- up/down counts by log2FoldChange sign
- validation consistency score
- top ranked statistical signals
- method support from DESeq2, edgeR, and limma-voom when available

It must not convert statistical signals into biological claims. Result-table
summaries are evidence review aids, not final scientific interpretations.

## Statistical Signal vs Biological Conclusion

Automated summaries must describe top genes as:

- ranked statistical signals
- candidate differentially expressed genes
- candidates requiring biological validation

They must not describe them as established biological mechanisms or causal
drivers. Domain review, experimental validation, study design review, and
independent evidence are required before stronger interpretation.

## Reliability Controls

Interpretation permissions depend on run status and reliability grade:

- Failed runs and grade E: interpretation is not allowed, and top genes are not
  displayed as conclusions.
- Grades C, D, and E: `strong_conclusion_allowed=false`, and the UI/report must
  display `当前证据不足以支持强科研结论。`
- `primary_method_status=completed_with_warning`: the interpretation layer keeps
  `strong_conclusion_allowed=false` and displays
  `主分析已完成，但存在方法学 warning，请谨慎解释结果。`
- Grade A is not allowed when the primary method completed only through a
  warning fallback.

These controls are intentionally stricter at the interpretation layer than a
plain table viewer.

## Evidence Output

Each evidence package now includes:

```text
12_interpretation_summary.md
```

The file records method status, reliability grade, significant gene counts, top
candidate statistical signals, validation consistency, guardrails, and strong
conclusion warnings.

The manifest registers this file, and `/projects/{project_id}/results` plus
`/coze/projects/{project_id}/report` expose:

- `interpretation_summary`
- `top_genes`
- `interpretation_guardrails`

## UI Review

The local `/ui` report view displays a Result Interpretation section with:

- total genes
- significant genes
- up/down counts
- validation consistency score
- Top candidate statistical signals
- guardrails

The UI intentionally avoids titles such as `Top biological findings`.

## Prohibited Automated Language

Automatic interpretation text must not use the following terms as conclusions:

- 证明
- 驱动
- 机制
- 关键致病基因
- 确定
- confirmed
- causal

These words may appear only in policy or documentation that defines prohibited
language. They must not appear in generated interpretation conclusions.

## What Did Not Change

- No new omics type was added.
- No FASTQ, alignment, quantification, Nextflow, or Snakemake support was added.
- DESeq2, edgeR, and limma-voom statistical logic was not changed.
- Dockerfile and R package installation behavior were not changed.
- Reliability core grading rules were not relaxed.
