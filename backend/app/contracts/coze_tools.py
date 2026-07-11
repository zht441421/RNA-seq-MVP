"""Stable Phase 8.2 tool contracts for a future Coze adapter."""

from copy import deepcopy


SCHEMA_VERSION = "8.2"
ERROR_BEHAVIOR = {
    "transport": "HTTP status with a sanitized JSON error body",
    "correlation_header": "X-Request-ID",
    "retryable_statuses": [429, 503],
    "non_retryable_statuses": [400, 401, 404, 409, 413, 422],
    "rules": [
        "Never expose credentials, local paths, commands, or stack traces.",
        "On 409, read task status and correct the lifecycle sequence.",
        "On 429, honor Retry-After before a bounded retry.",
    ],
}


def _object(properties: dict, required: list[str] | None = None) -> dict:
    value = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        value["required"] = required
    return value


_STRINGS = {"type": "array", "items": {"type": "string"}}
_STATUS = {"type": "string", "enum": [
    "created", "planned", "qc_placeholder_ready", "run_placeholder_ready",
    "report_placeholder_ready", "artifacts_placeholder_ready", "audit_placeholder_ready",
]}
_ARTIFACT = _object({
    "name": {"type": "string"}, "artifact_type": {"type": "string"},
    "path": {"type": "string", "description": "Safe task-relative reference."},
    "description": {"type": "string"}, "available": {"type": "boolean"},
}, ["name", "artifact_type", "path", "description", "available"])
_RESULT_FILE = _object({
    "artifact_name": {"type": "string"}, "artifact_type": {"type": "string"},
    "description": {"type": "string"},
    "download_url": {"type": "string", "description": "Relative API URL."},
    "available": {"type": "boolean"},
}, ["artifact_name", "artifact_type", "description", "download_url", "available"])


COZE_TOOL_DEFINITIONS = [
    {
        "name": "create_analysis_task",
        "purpose": "Create an analysis task and return its stable task identifier.",
        "http": {"method": "POST", "path": "/task/create", "operation_id": "coze_create_analysis_task"},
        "input_schema": _object({"task_type": {"type": "string", "default": "placeholder"}, "parameters": {"type": "object", "default": {}}}),
        "output_schema": _object({"task_id": {"type": "string"}, "status": _STATUS, "message": {"type": "string"}}, ["task_id", "status", "message"]),
        "error_behavior": ERROR_BEHAVIOR,
    },
    {
        "name": "validate_input",
        "purpose": "Validate metadata and count-matrix inputs without starting analysis.",
        "http": {"method": "POST", "path": "/task/validate-inputs", "operation_id": "coze_validate_analysis_inputs"},
        "input_schema": _object({"metadata_file": {"type": "string"}, "count_matrix_file": {"type": "string"}}, ["metadata_file", "count_matrix_file"]),
        "output_schema": _object({"status": {"type": "string"}, "valid": {"type": "boolean"}, "metadata": {"type": "object"}, "count_matrix": {"type": "object"}, "errors": _STRINGS, "limitations": _STRINGS}, ["status", "valid", "metadata", "count_matrix", "errors", "limitations"]),
        "error_behavior": ERROR_BEHAVIOR,
    },
    {
        "name": "start_analysis",
        "purpose": "Start an explicitly configured analysis after required task preparation.",
        "http": {"method": "POST", "path": "/task/run", "operation_id": "coze_run_analysis_task"},
        "lifecycle_preconditions": ["Task exists.", "Plan and QC preparation are complete.", "Inputs and explicit scientific choices are confirmed."],
        "input_schema": _object({
            "task_id": {"type": "string"}, "project_name": {"type": "string"},
            "omics_type": {"type": "string"}, "input_level": {"type": "string"},
            "analysis_goal": _STRINGS, "group_column": {"type": ["string", "null"]},
            "contrast": {"type": ["string", "null"]}, "contrast_column": {"type": ["string", "null"]},
            "contrast_numerator": {"type": ["string", "null"]}, "contrast_denominator": {"type": ["string", "null"]},
            "metadata_file": {"type": ["string", "null"]}, "count_matrix_file": {"type": ["string", "null"]},
            "execution_mode": {"type": ["string", "null"]}, "analysis_method": {"type": ["string", "null"]},
            "formal_de_method": {"type": ["string", "null"]},
        }, ["task_id", "project_name", "omics_type", "input_level"]),
        "output_schema": _object({"task_id": {"type": "string"}, "project_name": {"type": "string"}, "status": {"type": "string"}, "run_steps": {"type": "array", "items": {"type": "object"}}, "artifacts": {"type": "array", "items": {"type": "object"}}, "limitations": _STRINGS}, ["task_id", "project_name", "status", "run_steps", "artifacts", "limitations"]),
        "error_behavior": ERROR_BEHAVIOR,
    },
    {
        "name": "get_task_status",
        "purpose": "Read concise task lifecycle status for bounded polling.",
        "http": {"method": "GET", "path": "/task/{task_id}/status", "operation_id": "coze_query_task_status"},
        "input_schema": _object({"task_id": {"type": "string"}}, ["task_id"]),
        "output_schema": _object({"task_id": {"type": "string"}, "status": _STATUS, "message": {"type": "string"}}, ["task_id", "status", "message"]),
        "error_behavior": ERROR_BEHAVIOR,
    },
    {
        "name": "get_analysis_summary",
        "purpose": "Retrieve a sanitized task summary without creating scientific conclusions.",
        "http": {"method": "GET", "path": "/task/{task_id}/coze-summary", "operation_id": "coze_retrieve_result_summary"},
        "input_schema": _object({"task_id": {"type": "string"}}, ["task_id"]),
        "output_schema": _object({
            "task_id": {"type": "string"}, "status": {"type": "string"},
            "summary_message": {"type": "string"}, "reliability_information": {"type": "object"},
            "artifact_references": {"type": "array", "items": _RESULT_FILE},
            "sanitized_messages": {"type": "object"}, "warnings": _STRINGS,
            "limitations": _STRINGS, "interpretation_boundary": {"type": "string"},
            "safe_to_present": {"type": "boolean"},
        }, ["task_id", "status", "summary_message", "reliability_information", "artifact_references", "sanitized_messages", "warnings", "limitations", "interpretation_boundary", "safe_to_present"]),
        "error_behavior": ERROR_BEHAVIOR,
    },
    {
        "name": "list_artifacts",
        "purpose": "Discover task-scoped artifact metadata and availability.",
        "http": {"method": "GET", "path": "/task/{task_id}/artifacts", "operation_id": "coze_list_task_artifacts"},
        "input_schema": _object({"task_id": {"type": "string"}}, ["task_id"]),
        "output_schema": _object({"task_id": {"type": "string"}, "status": {"type": "string"}, "artifacts": {"type": "array", "items": _ARTIFACT}, "limitations": _STRINGS}, ["task_id", "status", "artifacts", "limitations"]),
        "error_behavior": ERROR_BEHAVIOR,
    },
    {
        "name": "download_artifact",
        "purpose": "Download one available artifact returned for the same task.",
        "http": {"method": "GET", "path": "/task/{task_id}/artifacts/{artifact_name}/download", "operation_id": "coze_download_task_artifact"},
        "input_schema": _object({"task_id": {"type": "string"}, "artifact_name": {"type": "string"}}, ["task_id", "artifact_name"]),
        "output_schema": {"type": "string", "format": "binary", "description": "Authenticated HTTP file response with a safe filename."},
        "error_behavior": ERROR_BEHAVIOR,
    },
]


def get_coze_tool_definitions() -> list[dict]:
    return deepcopy(COZE_TOOL_DEFINITIONS)


def build_coze_tool_manifest() -> dict:
    return {
        "manifest_name": "bioinformatics-agent-coze-tools",
        "manifest_version": SCHEMA_VERSION,
        "status": "preparation_only",
        "authentication": {"mode": "optional_api_key", "header_default": "X-Bioinfo-API-Key", "external_deployment_requirement": "Enable API-key authentication and TLS before exposure."},
        "tools": get_coze_tool_definitions(),
        "scientific_safety": {"agent_must_not": ["Invent methods, results, significance, or biological conclusions.", "Present exploratory output as formal differential expression.", "Ignore warnings, limitations, reliability information, or interpretation boundaries."]},
        "limitations": ["No Coze deployment or plugin publication is included.", "No public base URL or hosted input upload is configured.", "Existing lifecycle preparation endpoints remain required before analysis execution."],
    }
