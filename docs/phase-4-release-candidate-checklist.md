# Phase 4 Release Candidate Checklist

Use this checklist to review the Phase 4 release candidate freeze.

- [ ] Tests passed.
- [ ] Minimal demo script is available at `scripts/run_phase_4_4_demo.py`.
- [ ] DESeq2 demo script is available at `scripts/run_phase_4_9_deseq2_demo.py`.
- [ ] DESeq2 preflight is available through `GET /task/formal-de/preflight`.
- [ ] DESeq2 execution is gated by preflight readiness.
- [ ] DESeq2 interpretation summary is generated as `deseq2_interpretation_summary.json`.
- [ ] Coze response contract is documented.
- [ ] OpenAPI is unchanged or intentionally updated.
- [ ] No unsupported biological claims are made.
- [ ] No fake p-values or fake `padj` values are produced.
- [ ] No package installation is attempted.
- [ ] Safe error handling is preserved.
- [ ] Known limitations are listed.

## Known Limitations To Confirm

- `minimal_cpm_log2fc` is exploratory and does not produce p-values or adjusted
  p-values.
- DESeq2 requires local R/Rscript/BiocManager/DESeq2 readiness.
- No edgeR, limma, GO, KEGG, GSEA, pathway analysis, batch correction,
  visualization generation, database persistence, real Coze API integration, or
  multi-omics integration is included in this release candidate.
