# Reference Dataset and Golden Result Specification

## Classification model

- `workflow_fixture`: small synthetic or miniature input used only to verify
  parsing, lifecycle, safety, and deterministic workflow behavior.
- `reference_dataset`: versioned technical-validation data with documented
  provenance, usage terms, checksums, schemas, purpose, and limitations.
- `scientific_benchmark_dataset`: real public data with a source/accession,
  license or known usage terms, a defined benchmark question, and explicit
  scientific limitations.

Classification does not grant conclusion authority. A dataset is suitable for
scientific validation only when the manifest explicitly says so and its real
public provenance, terms, and benchmark design have been reviewed.

## Manifest contract

`reference-dataset-manifest.json` uses version `1.1` (while the validator keeps
version `1.0` compatibility) and supports multiple
dataset entries. Every entry records a stable identifier, type, classification,
data nature, source, usage terms, SHA-256 protected files, metadata and count
matrix schemas, contrast direction, expected counts, validation purpose,
limitations, scientific suitability, and a Golden Result reference. Paths are
repository-relative and never deployment filesystem paths.

The initial entry reuses `data/demo/rnaseq_minimal`. It is synthetic,
classified as `workflow_fixture`, and is unsuitable for scientific validation.
Phase 8.6 adds two `real_public` reference datasets with pinned source bytes,
deterministic preparation, explicit usage/citation terms, limited scientific
scope, and ignored local data storage. They are not declared scientific truth
benchmarks.

## Golden Result philosophy

Golden Results validate stable system behavior, not biological truth and not
fragile byte-for-byte output. Version `1.0` supports:

- exact checks for stable status, method, direction, flags, and fixed counts;
- set-based required artifact categories;
- inclusive numeric ranges;
- presence-only safety and explanation fields;
- accepted value sets;
- forbidden fields and unsupported claims;
- environment-dependent expectations such as real DESeq2 readiness.

Version `1.1` additionally supports explicit numeric tolerances, sign checks,
top-ranking overlap thresholds, unordered sets, finite-number checks, and safe
text-boundary checks. Floating-point tables, software-version-dependent values, timestamps, request
IDs, artifact ordering, and DESeq2 numeric results are intentionally not exact
Golden Result expectations.

For `minimal_cpm_log2fc`, Golden Results must require no p-values, no adjusted
p-values, no statistical-significance claims, and an exploratory interpretation
boundary. Synthetic fixtures must never be presented as scientific evidence.
