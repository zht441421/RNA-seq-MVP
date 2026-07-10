# Coze Tool Instructions Draft

Use this backend as a task lifecycle API for Bulk RNA-seq count matrix analysis.
These instructions are draft preparation notes for a future Coze tool and do
not publish or call a real Coze integration.

## Task Creation

Create a task when the user wants to start a new analysis session or has not
provided an existing `task_id`. Store the returned `task_id` for all later
calls.

## Input Registration

Register inputs after the user or deployment layer has placed metadata and
count matrix files under the configured input root. Use `input_role: metadata`
for the sample metadata file and `input_role: count_matrix` for the count matrix
file. Send only `source_relative_path` values, such as
`rnaseq_minimal/metadata.csv`.

## Minimal Workflow

Use `execution_mode: minimal_real` and `analysis_method: minimal_cpm_log2fc`
when the user wants the current deterministic minimal workflow. Explain that
this workflow produces exploratory CPM/log2FC ranking and does not provide
p-values or adjusted p-values.

## DESeq2

Call `GET /task/formal-de/preflight` before requesting DESeq2. Request DESeq2
only when the user asks for it and preflight readiness is true. Use
`execution_mode: formal_de_real`, `analysis_method: deseq2`, and
`formal_de_method: deseq2`. If preflight readiness is false, explain that DESeq2
was not run.

## Coze Summary

Always call `GET /task/{task_id}/coze-summary` before presenting results. Use
`summary_message`, `warnings`, `limitations`, `contrast`, and `download_links`
as the main user-facing source. Do not summarize raw result tables unless a
future phase explicitly adds that behavior.

## Log2FC Direction

When explicit contrast fields are available, explain direction this way:
positive log2FC means higher in `contrast_numerator` relative to
`contrast_denominator`; negative log2FC means lower in `contrast_numerator`
relative to `contrast_denominator`.

## Missing Inputs And Invalid Contrast

If the backend reports missing inputs, ask for both metadata and count matrix
registration before running. If the backend reports invalid contrast, ask the
user to confirm the comparison column, treatment group, and control group
exactly as they appear in metadata.

## Artifact Downloads

Present artifact downloads using relative API paths returned by `coze-summary`
or the artifact endpoints. A deployment layer may combine those paths with a
public base URL later. Do not show local deployment paths.

## Claims To Avoid

Do not claim biological significance without user validation. Do not claim
enrichment output if enrichment was not run. Do not claim p-values for the
minimal workflow. Do not claim DESeq2 ran if preflight readiness failed or the
run did not complete. Do not claim edgeR, limma, GO, KEGG, or GSEA output in
this phase.
