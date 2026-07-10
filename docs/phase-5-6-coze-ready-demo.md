# Phase 5.6 Coze-Ready Demo

Phase 5.6 adds a reproducible backend-only demo that validates the current
Coze-ready task lifecycle. It uses the minimal CPM/log2FC workflow so it does
not require R, Rscript, BiocManager, DESeq2, Docker, workflow engines, frontend
code, or real Coze API calls.

## Purpose

The demo proves that a client can:

1. create a task
2. register metadata and count matrix inputs
3. run `minimal_cpm_log2fc` with an explicit contrast
4. fetch task status
5. list artifacts
6. download `report.md`
7. download `differential_expression_results.csv`
8. fetch `coze-summary`
9. verify public responses are safe for Coze or front-end presentation

## Demo Command

```powershell
python scripts\run_phase_5_6_coze_ready_demo.py
```

Expected success output includes:

```text
Phase 5.6 Coze-ready demo validation passed
- task created
- inputs registered
- run completed
- artifacts verified
- downloads verified
- coze summary verified
```

The script exits with code `0` on success. If demo data is missing, it exits
non-zero with a deterministic message naming the missing safe relative demo
file.

## Demo Data

The guaranteed demo uses:

```text
data/demo/rnaseq_minimal/metadata.csv
data/demo/rnaseq_minimal/counts.csv
```

The script sets `BIOINFO_INPUT_ROOT` to `data/demo` by default and registers:

```text
rnaseq_minimal/metadata.csv
rnaseq_minimal/counts.csv
```

## Output And State

Default generated output directory:

```text
data/outputs/phase_5_6_coze_ready_demo/
```

Default transient task store:

```text
data/state/phase_5_6_demo_tasks.sqlite3
```

Both locations are intended as generated demo state and should not be committed.

## Contrast Direction

The demo uses the first two condition values in the demo metadata and runs with
an explicit contrast:

```json
{
  "contrast_column": "condition",
  "contrast_numerator": "treatment",
  "contrast_denominator": "control"
}
```

The demo verifies that artifacts and Coze summary include:

- `contrast`
- `direction`
- `positive_log2fc_interpretation`
- `negative_log2fc_interpretation`

For the bundled demo data, positive log2FC means higher expression in
`treatment` relative to `control`.

## Artifact Downloads

The demo verifies the safe artifact download endpoint:

```text
GET /task/{task_id}/artifacts/report.md/download
GET /task/{task_id}/artifacts/differential_expression_results.csv/download
```

Download URLs exposed in `coze-summary` must be relative API paths, not local
absolute paths or external URLs.

## Coze Summary Behavior

The demo verifies `GET /task/{task_id}/coze-summary` includes:

- `summary_message`
- `result_files`
- `download_links`
- `contrast`
- `positive_log2fc_interpretation`
- `negative_log2fc_interpretation`
- `warnings`
- `limitations`
- `safe_to_present`
- `registered_inputs`

The expected `safe_to_present` value is `true`.

## Safety Checks

The script asserts public JSON responses and downloaded text do not expose:

- `D:\`
- `C:\`
- `/home/`
- `/mnt/`
- `file://`
- `traceback`
- `token`
- `password`
- `secret`

It also asserts that public download links are relative API paths.

## Limitations

- The demo validates `minimal_cpm_log2fc`, not DESeq2.
- No R or Bioconductor availability is required.
- No edgeR, limma, or enrichment analysis is added.
- No frontend or real Coze call is added.
- The minimal workflow remains exploratory and does not produce formal
  differential expression statistics.

## Future Coze Integration Notes

A future Coze integration can call the same backend lifecycle using uploaded or
pre-registered task inputs. If DESeq2 preflight is ready, a future optional demo
may validate DESeq2, but Phase 5.6 intentionally guarantees only the
R-independent minimal workflow.
