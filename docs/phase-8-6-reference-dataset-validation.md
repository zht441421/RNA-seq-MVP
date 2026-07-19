# Phase 8.6 Real Public Reference Dataset Validation

## Scope and scientific boundary

Phase 8.6 validates the existing bulk RNA-seq MVP against two independent real
public count datasets. It exercises existing APIs locally and through the Phase
8.5 protected local staging boundary. It adds no analysis algorithm, changes no
RNA-seq or DESeq2 execution behavior, performs no remote deployment, and does
not integrate or publish a Coze plugin.

A passing Golden Result detects a system regression boundary; it does not prove
biological truth, statistical significance, clinical validity, or causal
interpretation. The exercised method is the existing exploratory
`minimal_cpm_log2fc` path, which intentionally reports no p-values or adjusted
p-values. No GO, KEGG, GSEA, batch correction, or complex-design inference is
performed.

## Versioned datasets

### `phase-8-6-pasilla-public-v1`

- Source: Bioconductor `pasilla` 1.40.0, with underlying GEO GSE18508.
- Material: seven Drosophila S2-cell libraries, treated versus untreated.
- Prepared shape: 14,599 genes by seven samples.
- Terms: Bioconductor package LGPL; source attribution and underlying GEO and
  modENCODE terms remain controlling.
- Citation: Brooks AN et al., Genome Research 2011, PMID 20921232; Bioconductor
  DOI `10.18129/B9.bioc.pasilla`.

### `phase-8-6-gse60450-luminal-public-v1`

- Source: NCBI GEO GSE60450 pinned supplementary counts and series metadata.
- Material: four mouse mammary luminal samples selected by accession: two
  virgin and two day-2 lactating samples.
- Prepared shape: 27,179 genes by four samples.
- Terms: GEO states no separate dataset license; NCBI policies, submitter rights,
  attribution, and citation requirements apply. The project does not relicense
  the data or assert unrestricted rights.
- Citation: Fu NY et al., Nature Cell Biology 2015, PMID 25730472.

The exact source URLs, source byte sizes, SHA-256 values, accessions, retrieval
date, sample selection, schemas, preprocessing rules, prepared-file SHA-256
values, limitations, and validation scope are recorded in
`docs/reference-datasets/reference-dataset-manifest.json`.

## Reproducible retrieval and preprocessing

Source and prepared data are generated locally and ignored by Git. Retrieval
accepts credential-free HTTPS only, writes through a temporary file, and checks
both declared size and SHA-256 before use.

```text
python scripts\fetch_phase_8_6_reference_datasets.py --list
python scripts\fetch_phase_8_6_reference_datasets.py --all
python scripts\prepare_phase_8_6_reference_datasets.py --all
```

Preparation fixes sample and gene ordering, rejects missing, negative, or
non-integer counts, sums duplicate gene identifiers, and retains zero-count
genes. Pasilla sample identifiers are normalized by the declared suffix rule.
GSE60450 uses only the four declared accession-linked source columns. There is
no hidden gene filtering or biological transformation.

## Golden Result strategy

Stable contract fields, terminal state, sample/gene counts, method, contrast,
and scientific-safety flags are exact. Selected rounded log2 fold changes use
explicit numeric tolerances; selected directions use sign comparisons; the
top-20 ranking permits a documented overlap threshold; artifact categories are
set-based; every exposed ranking value must be finite. Unsupported significance,
causation, and enrichment-completion text is forbidden.

DESeq2 is environment-dependent. The runner calls the real preflight endpoint.
If unavailable, DESeq2 validation is explicitly skipped and confidence is
limited. If ready, preflight readiness is recorded but is not misrepresented as
a completed DESeq2 execution. Phase 8.6 never simulates formal DESeq2 success.

## Local and protected-staging execution

Run one dataset, both datasets, and a repeat to compare stable observations:

```text
python scripts\run_phase_8_6_reference_validation.py --list
python scripts\run_phase_8_6_reference_validation.py --dataset phase-8-6-pasilla-public-v1 --mode local
python scripts\run_phase_8_6_reference_validation.py --all --mode local
```

For protected staging, first prepare Phase 8.5 secrets, then add the Phase 8.6
isolated read-only input mount and scoped input-root override. Run the Phase 8.5
smoke against the base compose stack separately before this override when both
regression paths are required.

```text
python scripts\prepare_phase_8_5_local_staging.py
docker compose -f docker-compose.staging.yml -f deploy/staging/phase-8-6.compose.yml up --build -d
python scripts\smoke_phase_8_5_protected_staging.py
python scripts\run_phase_8_6_reference_validation.py --all --mode staging
docker compose -f docker-compose.staging.yml -f deploy/staging/phase-8-6.compose.yml restart
python scripts\run_phase_8_6_reference_validation.py --all --mode staging
docker compose -f docker-compose.staging.yml -f deploy/staging/phase-8-6.compose.yml down
```

The staging client accepts only local HTTPS, reads the API key from the ignored
secret file, sends it only in the configured header, and never writes it to a
report. Authentication, rate limiting, request limits, observability, audit
events, task-scoped artifact discovery, and safe artifact downloads remain the
existing backend responsibilities.

## Reports, reproducibility, and failure meaning

Generated reports live under ignored `.staging-runtime/phase-8-6-validation`.
They record dataset/source/preprocessing versions, prepared checksums, repository
commit, execution environment, contrast, method, terminal state, Golden Result
checks, reliability, warnings, limitations, artifact inventory, audit event
types, DESeq2 preflight policy, skipped checks, and whether a previous run was
available. They contain no credentials, internal stack traces, or local absolute
paths.

A repeat compares stable summary fields, artifact sets, warnings, limitations,
interpretation boundary, method and direction, top-20 overlap, and selected gene
signs. A failure means that the declared regression boundary changed or the
workflow failed; it is not itself evidence that the biological source is wrong.

Run the offline structure and full regression gate with:

```text
python scripts\verify_phase_8_6_reference_dataset_validation.py
```

With downloaded data and a running protected stack, add `--real-data --staging`.
Standard `pytest` remains offline and does not download public data.

## Limitations and next phase

The datasets are limited two-group technical references, not independent truth
standards. The minimal method has no inferential statistics. Dataset-specific
upstream processing and the selected GSE60450 subset can affect observed
rankings. Phase 8.7 remains the future real Coze end-to-end integration stage;
it requires a separate explicit authorization, protected credentials, and its
own deployment and publication gates.
