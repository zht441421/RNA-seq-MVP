# Coze Frontend Flow

Coze acts as the user-facing workflow layer. The FastAPI backend owns file
inspection, QC, planning, execution orchestration, artifact generation, and
reliability grading.

## Flow

1. Create project.
2. Upload or register count matrix and metadata files.
3. Inspect files and detect candidate schema fields.
4. Ask user to confirm:
   - `sample_id_column`
   - `gene_id_column`
   - `group_column`
   - `reference_group`
   - `test_group`
   - optional `batch_column`
   - optional `covariates`
5. Run QC.
6. Show QC summary and blocking issues, if any.
7. Generate method recommendation.
8. Show analysis plan.
9. Require explicit user confirmation.
10. Run mock analysis pipeline.
11. Show status and result summary.
12. Provide downloadable report and evidence package.

## Coze Conversation Guardrails

- Coze should not infer final biological conclusions from uploaded data.
- Coze should present QC findings as checks, warnings, or blockers.
- Coze should require user confirmation before running analysis.
- Coze should show reliability grade with any generated result.
- Coze should state when results are mock or placeholder outputs.

## Backend State Transitions

```text
created
  -> files_uploaded
  -> inspected
  -> qc_completed
  -> plan_proposed
  -> plan_confirmed
  -> running
  -> completed
```

Failed checks may move a project to `failed` or keep it in a state where the
user can correct inputs and retry.

