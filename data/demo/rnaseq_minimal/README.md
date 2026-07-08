# Minimal RNA-seq Demo Data

This directory contains small synthetic test data for validating the minimal
Bulk RNA-seq MVP workflow. The values are designed for deterministic acceptance
checks only and are not a biological claim.

## Files

- `metadata.csv` lists six samples with `sample_id` and `condition` columns.
- `counts.csv` is a gene-by-sample count matrix. The first column is `gene_id`,
  and the remaining columns match the sample IDs in `metadata.csv`.

The demo contains two conditions with three samples each:

- `control`
- `treatment`

At least one low-count gene is included so the existing total-count filter can
be validated.

## Expected Outputs

Running the Phase 4.4 demo script should produce:

- `run_manifest.json`
- `execution_summary.json`
- `qc_summary.json`
- `normalized_counts_cpm.csv`
- `differential_expression_results.csv`
- `report.md`

The MVP computes QC metrics, CPM-normalized counts, and an exploratory log2
fold-change ranking. No formal differential expression statistics are produced.
