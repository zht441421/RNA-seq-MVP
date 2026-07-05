# Phase 1 MVP Scope

## In Scope

Phase 1 supports only Bulk RNA-seq differential expression workflows where the
user provides:

- A gene by sample count matrix.
- A sample metadata table.
- Group and contrast settings.
- Optional batch and covariate settings.

The backend supports:

- File readability checks.
- Schema inspection and field recommendation.
- Sample ID alignment between count matrix and metadata.
- Count value checks.
- Group and contrast checks.
- Batch and group confounding warnings.
- Library size and low-count gene summaries.
- Analysis plan recommendation.
- User confirmation gate before analysis.
- Mock DESeq2 primary analysis runner.
- Mock edgeR and limma-voom validation runners.
- Markdown report and evidence package placeholders.
- Reliability grading and audit notes.

## Out of Scope

Phase 1 does not support:

- FASTQ upload.
- Read trimming.
- Alignment.
- Quantification.
- Transcript abundance import.
- Single-cell RNA-seq.
- Proteomics, metabolomics, epigenomics, or multi-omics integration.
- Real R/Bioconductor execution.
- Real statistical result interpretation.

## Method Placeholders

The intended future primary method is DESeq2. The intended future validation
methods are edgeR and limma-voom. In Phase 1, these are interface contracts and
mock outputs only.

## Safety Boundary

The system may summarize QC status, plan recommendations, and reliability grade.
It must not make strong biological or clinical claims unless the reliability
grade permits strong conclusions.

