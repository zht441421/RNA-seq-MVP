# Phase 8.3 Coze Workflow Simulation and Local Agent Integration Test

## Scope

Phase 8.3 validates the future Coze interaction flow locally without an LLM,
Coze deployment, plugin publication, public endpoint, or new API route. The
lightweight simulator is `backend/app/services/local_agent_simulator.py`. It
uses an injected HTTP client so tests call the real FastAPI application and
therefore retain authentication, request limits, rate limiting, observability,
audit tracing, lifecycle guards, and artifact security.

Run `python scripts/verify_phase_8_3_local_agent_simulation.py` to verify the
simulator, documentation, Phase 8.2 manifest compatibility, and full pytest
suite. Use `--skip-tests` only for a quick structural check.

## Simulator design

The simulator is deterministic and does not interpret free-form scientific
questions. It maps seven exact local intents to the seven reviewed Phase 8.2
tools, validates required/unknown arguments against their manifest schemas,
expands only declared path parameters, and invokes the existing HTTP bindings.
Each invocation returns this stable simulation envelope:

```json
{
  "tool_name": "get_task_status",
  "ok": true,
  "status_code": 200,
  "request_id": "opaque-request-id",
  "data": {
    "task_id": "task_0001",
    "status": "run_placeholder_ready",
    "message": "Analysis execution completed."
  },
  "error": null
}
```

Local lifecycle preparation operations are labeled `register_metadata`,
`register_count_matrix`, `prepare_plan`, and `prepare_qc`; they call the
existing APIs and are not presented as new Phase 8.2 tools.

## Simulated workflow and tool sequence

1. Agent request `create task` selects `create_analysis_task`.
2. Register safe metadata and count-matrix references through the existing
   task input endpoint.
3. Agent request `validate input` selects `validate_input`.
4. Call existing plan and QC preparation endpoints.
5. Agent request `start analysis` selects `start_analysis` with explicit method
   and contrast direction.
6. Agent request `check status` selects `get_task_status` for bounded polling.
7. Agent request `get summary` selects `get_analysis_summary`.
8. Agent request `list artifacts` selects `list_artifacts`.
9. When requested, `download artifact` selects `download_artifact` using an
   available artifact name returned for the same task.

The local minimal workflow is synchronous, but the simulator still implements
a bounded poll count to model future asynchronous integration safely.

## Example agent request and input

```json
{
  "project_name": "phase_8_3_local_agent",
  "omics_type": "bulk_rnaseq",
  "input_level": "count_matrix",
  "metadata_file": "rnaseq_minimal/metadata.csv",
  "count_matrix_file": "rnaseq_minimal/counts.csv",
  "sample_id_column": "sample_id",
  "group_column": "condition",
  "contrast_numerator": "treatment",
  "contrast_denominator": "control",
  "execution_mode": "minimal_real",
  "analysis_method": "minimal_cpm_log2fc"
}
```

Input references are safe paths relative to the configured input root; they are
not operating-system paths and are never converted into public local paths.

## Example successful workflow response

```json
{
  "simulation": "phase-8.3-local-agent",
  "completed": true,
  "task_id": "task_0001",
  "summary": {
    "status": "run_placeholder_ready",
    "analysis_method": "minimal_cpm_log2fc",
    "statistical_test_performed": false,
    "safe_to_present": true,
    "reliability_information": {
      "available": false,
      "grade": null,
      "strong_conclusion_allowed": false
    }
  },
  "artifacts": {
    "task_id": "task_0001",
    "artifacts": [
      {
        "name": "report.md",
        "path": "tasks/task_0001/report.md",
        "available": true
      }
    ]
  },
  "scientific_conclusion_generated": false
}
```

The actual response also includes every structured step and preserves the full
summary warnings, limitations, artifact references, interpretation boundary,
and reliability information.

## Example structured failure

```json
{
  "tool_name": "get_task_status",
  "ok": false,
  "status_code": 400,
  "request_id": null,
  "data": null,
  "error": {
    "code": "INVALID_TOOL_ARGUMENTS",
    "message": "Missing required tool arguments: task_id"
  }
}
```

HTTP failures use `TOOL_HTTP_ERROR`, preserve the response status and opaque
request ID, and retain only sanitized backend details. Transport failures use a
neutral message. The simulator never returns stack traces, credentials,
configuration, commands, or storage roots.

## Reliability and scientific boundaries

The simulator copies reliability information directly from the backend safe
summary. Missing reliability remains `available: false` and
`strong_conclusion_allowed: false`. It does not synthesize a grade or convert
exploratory CPM/log2FC rankings into formal differential expression. The
workflow response always declares `scientific_conclusion_generated: false`;
future AI presentation must preserve method flags, warnings, limitations, and
the interpretation boundary.

## Limitations

- No LLM, Coze SDK, real Coze plugin, publication, or deployment is included.
- No public base URL, hosted upload, OAuth flow, or cloud service is included.
- The simulator is an integration-test harness, not a production scheduler.
- Polling is bounded but does not add a background queue or workflow engine.
- Only existing Bulk RNA-seq capabilities are exercised; analysis behavior is
  unchanged.
