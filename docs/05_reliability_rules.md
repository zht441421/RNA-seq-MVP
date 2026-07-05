# Reliability Rules

Reliability grade gates how strongly the system may phrase conclusions.

## Grades

| Grade | Meaning | Strong Conclusion Allowed |
| --- | --- | --- |
| A | High reliability. QC passed, adequate design, validation concordant, audit complete. | Yes |
| B | Good reliability. QC passed with minor limitations, at least one validation method supports the primary result. | Yes, with limitations |
| C | Exploratory reliability. QC passed, but validation is missing, mock, or incomplete. | No |
| D | Low reliability. Major design or QC limitations exist, but analysis may be run for debugging or exploration. | No |
| E | Unreliable or blocked. Stop conditions are present. | No |

## Stop Conditions

Any stop condition yields grade E until resolved:

- Count matrix cannot be read.
- Metadata cannot be read.
- Required columns are missing.
- Count matrix sample columns and metadata sample IDs do not align.
- Count values are negative or non-numeric.
- Group column is missing.
- Reference group or test group is absent.
- No samples exist for one side of the contrast.

## Downgrade Conditions

Downgrade conditions reduce reliability:

- Fewer than 2 samples in a contrast group.
- Strong batch and group confounding.
- Many non-integer count-like values.
- Very uneven library sizes.
- Excessive low-count genes.
- Missing validation method outputs.
- Validation outputs disagree with the primary method.
- Missing audit artifacts.

## Strong Conclusion Rules

Strong conclusions are allowed only when:

- Reliability grade is A or B.
- QC has no stop conditions.
- The analysis plan was confirmed by the user.
- Primary and validation methods are available and concordant.
- Report includes method, thresholds, design formula, and limitations.

For grades C, D, and E, generated text must use exploratory language and must
avoid definitive biological or clinical claims.

## Evidence Package Gating

`01_summary.md` and `11_reliability_report.md` must respect the final
reliability grade.

Allowed conclusion levels:

- A: statistical conclusions may be stated with limitations; causal language is
  prohibited.
- B: only cautious supportive conclusions are allowed.
- C: exploratory findings only.
- D: not recommended for formal conclusions.
- E: no scientific conclusion.

For grades C, D, and E, `01_summary.md` must include:

```text
Current evidence is not sufficient for a strong scientific conclusion.
```

No generated report may describe correlation or differential expression as a
causal mechanism.

## Real R Runner Rules

When `RUN_MODE=real_r` or `RUN_MODE=docker_r`, reliability is based on
`run_status.json` plus QC and audit artifacts.

The environment can be checked with `GET /system/r-env`. A missing Rscript or
missing required R package must not be interpreted as a successful real run.

Grade A requires:

- QC passed.
- DESeq2 completed.
- At least one validation method completed.
- `validation_consistency_score >= 0.8`.
- FDR was applied.
- `r_session_info.txt` exists.
- Audit log exists.

Grade B requires:

- QC passed or only minor warnings are present.
- DESeq2 completed.
- At least one validation method completed.
- `validation_consistency_score >= 0.6`.

Grade C applies when:

- DESeq2 completed, but validation was skipped or failed.
- Validation consistency is unavailable or below threshold.
- Results must be described as exploratory only.

Grade D applies when:

- DESeq2 completed, but serious QC/design warnings exist.
- Batch and group appear strongly confounded.
- Contrast group sample size is too low.

Grade E applies when:

- Rscript is unavailable.
- Docker is unavailable for `docker_r`.
- The configured Docker image is unavailable for `docker_r`.
- Required real-run packages are missing and DESeq2 cannot run.
- DESeq2 failed.
- Input data are unavailable or invalid.
- `run_status.json` is missing or invalid.
- Results are not reproducible.

The backend never installs R packages automatically. If environment validation
fails, the result must be operational guidance only, not a scientific
conclusion.

Even when `RUN_MODE=real_r` fails, the evidence package must still include
summary, QC report, method report, audit log, reliability report, and manifest
so that the failure is reproducible and auditable.

The same evidence package requirement applies to `RUN_MODE=docker_r`. Docker
image availability, image name, package versions when available, and Docker
availability must be captured in `10_audit_log.json`.
