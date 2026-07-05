# Phase 1.10 Reproducibility Package + Run Replay

Phase 1.10 adds a reproducibility bundle to every evidence package and provides
a dry-run replay helper.

This phase does not change:

- supported omics types
- DESeq2, edgeR, or limma-voom statistical logic
- Dockerfile
- reliability grading rules

## Reproducibility Bundle

Each run writes:

```text
08_reproducible_code/
  README_REPRODUCE.md
  analysis_config.json
  run_command.txt
  docker_command.txt
  input_hashes.json
  software_versions.json
```

These files are included in `manifest.json` and shown in the local `/ui`
Artifact Review panel.

## Input Hashes

`input_hashes.json` records:

```json
{
  "count_matrix_path": "...",
  "count_matrix_sha256": "...",
  "metadata_path": "...",
  "metadata_sha256": "...",
  "analysis_config_sha256": "..."
}
```

Hashes are computed from host-side files. If a file is unavailable, the hash is
`null` and a warning is recorded in the JSON. Hash failures do not crash report
generation.

## Software Versions

`software_versions.json` records run mode, Docker image, R version when
available, and R package versions from `run_status.json`.

For `docker_r`, the Docker image is recorded as:

```text
bioinformatics-agent-r-bulk-rnaseq:0.1
```

## Replay Dry Run

The replay helper is dry-run by default:

```bash
python scripts/replay_from_artifact.py artifacts/<project_id>
```

or:

```bash
python scripts/replay_from_artifact.py <project_id>
```

Dry-run prints the Docker command and the planned replay output directory. It
does not write files and does not execute Docker.

## Execute Replay

To execute:

```bash
python scripts/replay_from_artifact.py artifacts/<project_id> --execute
```

Execution writes a new replay analysis config and outputs to:

```text
artifacts/<project_id>_replay_<timestamp>
```

The original artifact package is not overwritten or deleted.

## Replay Boundary

Replay reproduces the computational workflow. It does not automatically create
new scientific validation, improve QC, or upgrade the reliability grade.

Any conclusion still depends on:

- QC status
- study design
- sample size
- validation method completion
- validation consistency
- reliability grade

Replay is therefore an audit and reproducibility tool, not a substitute for
biological review or independent validation.

