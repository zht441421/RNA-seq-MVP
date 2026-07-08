# Phase 4.9 DESeq2 Minimal Demo Data

This directory contains synthetic demo data for validating the Phase 4.9
DESeq2 end-to-end pipeline path.

Files:

- `metadata.csv`
- `counts.csv`

The dataset has six synthetic samples, with three `control` samples and three
`treated` samples. The count matrix has `gene_id` as the first column and the
sample columns exactly match `metadata.csv`.

These values are synthetic demo data, not real biological data. Results from
this dataset are for pipeline validation only and are not for biological interpretation.

No GO, KEGG, GSEA, pathway analysis, visualization, batch correction, or complex
design formula is represented by these files.
