"""Deterministic local simulation of future agent-to-tool interaction.

The simulator has no LLM and adds no API routes. An HTTP-compatible client is
injected so tests can exercise the real FastAPI middleware and route contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

from backend.app.contracts.coze_tools import get_coze_tool_definitions
from backend.app.services.coze_summary import sanitize_summary_payload


class HTTPResponse(Protocol):
    status_code: int
    headers: Any
    content: bytes

    def json(self) -> Any: ...


class HTTPClient(Protocol):
    def request(self, method: str, url: str, **kwargs: Any) -> HTTPResponse: ...


@dataclass(frozen=True)
class AgentToolResult:
    tool_name: str
    ok: bool
    status_code: int
    request_id: str | None
    data: Any = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return sanitize_summary_payload(
            {
                "tool_name": self.tool_name,
                "ok": self.ok,
                "status_code": self.status_code,
                "request_id": self.request_id,
                "data": self.data,
                "error": self.error,
            }
        )


class LocalAgentSimulator:
    """Select and invoke reviewed tools through an injected local HTTP client."""

    _INTENT_TO_TOOL = {
        "create task": "create_analysis_task",
        "validate input": "validate_input",
        "start analysis": "start_analysis",
        "check status": "get_task_status",
        "get summary": "get_analysis_summary",
        "list artifacts": "list_artifacts",
        "download artifact": "download_artifact",
    }

    def __init__(self, client: HTTPClient) -> None:
        self.client = client
        self.tools = {
            definition["name"]: definition
            for definition in get_coze_tool_definitions()
        }

    def select_tool(self, agent_request: str) -> str:
        normalized = " ".join(str(agent_request).strip().lower().split())
        tool_name = self._INTENT_TO_TOOL.get(normalized)
        if tool_name is None:
            raise ValueError("Unsupported local agent request.")
        return tool_name

    def handle_request(
        self, agent_request: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            tool_name = self.select_tool(agent_request)
        except ValueError as exc:
            return AgentToolResult(
                tool_name="unsupported",
                ok=False,
                status_code=400,
                request_id=None,
                error={"code": "UNSUPPORTED_AGENT_REQUEST", "message": str(exc)},
            ).to_dict()
        return self.invoke_tool(tool_name, arguments)

    def invoke_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        definition = self.tools.get(tool_name)
        if definition is None:
            return self._local_error(
                tool_name, "UNKNOWN_TOOL", "Requested tool is not defined by the manifest."
            )
        validation_error = self._validate_arguments(definition, arguments)
        if validation_error is not None:
            return self._local_error(tool_name, "INVALID_TOOL_ARGUMENTS", validation_error)

        binding = definition["http"]
        path = binding["path"]
        body = dict(arguments)
        for parameter in ("task_id", "artifact_name"):
            placeholder = "{" + parameter + "}"
            if placeholder in path:
                path = path.replace(
                    placeholder, quote(str(body.pop(parameter)), safe="")
                )

        request_kwargs: dict[str, Any] = {}
        if binding["method"] != "GET":
            request_kwargs["json"] = body
        try:
            response = self.client.request(binding["method"], path, **request_kwargs)
        except Exception:
            return self._local_error(
                tool_name,
                "LOCAL_TRANSPORT_ERROR",
                "Local tool request could not be completed.",
                status_code=503,
            )
        request_id = response.headers.get("x-request-id")
        if 200 <= response.status_code < 300:
            data = self._success_data(tool_name, response)
            return AgentToolResult(
                tool_name=tool_name,
                ok=True,
                status_code=response.status_code,
                request_id=request_id,
                data=data,
            ).to_dict()
        return AgentToolResult(
            tool_name=tool_name,
            ok=False,
            status_code=response.status_code,
            request_id=request_id,
            error=self._response_error(response),
        ).to_dict()

    def simulate_workflow(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run one complete local minimal-analysis agent interaction."""

        steps: list[dict[str, Any]] = []
        required = (
            "project_name",
            "metadata_file",
            "count_matrix_file",
            "sample_id_column",
            "group_column",
            "contrast_numerator",
            "contrast_denominator",
        )
        missing = [name for name in required if not request.get(name)]
        if missing:
            steps.append(
                self._local_error(
                    "simulation_request",
                    "INVALID_WORKFLOW_REQUEST",
                    "Missing required workflow fields: " + ", ".join(missing),
                )
            )
            return self._workflow_result(None, steps)
        created = self.invoke_tool("create_analysis_task", {})
        steps.append(created)
        if not created["ok"]:
            return self._workflow_result(None, steps)
        task_id = created["data"]["task_id"]

        for role, path_key in (
            ("metadata", "metadata_file"),
            ("count_matrix", "count_matrix_file"),
        ):
            registered = self._invoke_support_api(
                f"register_{role}",
                "POST",
                f"/task/{quote(task_id, safe='')}/inputs/register",
                {"input_role": role, "source_relative_path": request[path_key]},
            )
            steps.append(registered)
            if not registered["ok"]:
                return self._workflow_result(task_id, steps)

        validated = self.invoke_tool(
            "validate_input",
            {
                "metadata_file": request["metadata_file"],
                "count_matrix_file": request["count_matrix_file"],
            },
        )
        steps.append(validated)
        if not validated["ok"] or not validated["data"].get("valid"):
            return self._workflow_result(task_id, steps)

        plan_payload = self._plan_payload(task_id, request)
        planned = self._invoke_support_api("prepare_plan", "POST", "/task/plan", plan_payload)
        steps.append(planned)
        if not planned["ok"]:
            return self._workflow_result(task_id, steps)

        qc_payload = {
            **plan_payload,
            "metadata_file": request["metadata_file"],
            "count_matrix_file": request["count_matrix_file"],
            "sample_id_column": request["sample_id_column"],
        }
        qc_ready = self._invoke_support_api("prepare_qc", "POST", "/task/qc", qc_payload)
        steps.append(qc_ready)
        if not qc_ready["ok"]:
            return self._workflow_result(task_id, steps)

        run_payload = {
            **plan_payload,
            "execution_mode": request.get("execution_mode", "minimal_real"),
            "analysis_method": request.get("analysis_method", "minimal_cpm_log2fc"),
            "contrast_column": request["group_column"],
            "contrast_numerator": request["contrast_numerator"],
            "contrast_denominator": request["contrast_denominator"],
        }
        started = self.invoke_tool("start_analysis", run_payload)
        steps.append(started)
        if not started["ok"]:
            return self._workflow_result(task_id, steps)

        try:
            max_polls = max(1, min(int(request.get("max_status_polls", 3)), 10))
        except (TypeError, ValueError):
            steps.append(
                self._local_error(
                    "get_task_status",
                    "INVALID_POLL_CONFIGURATION",
                    "Status poll limit must be an integer.",
                )
            )
            return self._workflow_result(task_id, steps)
        status_result = None
        for _ in range(max_polls):
            status_result = self.invoke_tool("get_task_status", {"task_id": task_id})
            steps.append(status_result)
            if not status_result["ok"]:
                return self._workflow_result(task_id, steps)
            if status_result["data"].get("status") == "run_placeholder_ready":
                break
        if status_result is None or status_result["data"].get("status") != "run_placeholder_ready":
            steps.append(self._local_error("get_task_status", "POLL_LIMIT_REACHED", "Task did not reach the expected completed state within the poll limit.", 408))
            return self._workflow_result(task_id, steps)

        summary = self.invoke_tool("get_analysis_summary", {"task_id": task_id})
        steps.append(summary)
        if not summary["ok"]:
            return self._workflow_result(task_id, steps)
        artifacts = self.invoke_tool("list_artifacts", {"task_id": task_id})
        steps.append(artifacts)
        return self._workflow_result(task_id, steps, summary, artifacts)

    @staticmethod
    def _plan_payload(task_id: str, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "project_name": request["project_name"],
            "omics_type": request.get("omics_type", "bulk_rnaseq"),
            "input_level": request.get("input_level", "count_matrix"),
            "analysis_goal": request.get("analysis_goal", ["qc", "differential_expression"]),
            "group_column": request["group_column"],
            "contrast": f"{request['contrast_numerator']}_vs_{request['contrast_denominator']}",
        }

    def _invoke_support_api(
        self, name: str, method: str, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            response = self.client.request(method, path, json=payload)
        except Exception:
            return self._local_error(name, "LOCAL_TRANSPORT_ERROR", "Local lifecycle preparation request could not be completed.", 503)
        request_id = response.headers.get("x-request-id")
        if 200 <= response.status_code < 300:
            return AgentToolResult(name, True, response.status_code, request_id, self._json_body(response)).to_dict()
        return AgentToolResult(name, False, response.status_code, request_id, error=self._response_error(response)).to_dict()

    @staticmethod
    def _validate_arguments(definition: dict[str, Any], arguments: object) -> str | None:
        if not isinstance(arguments, dict):
            return "Tool arguments must be an object."
        schema = definition["input_schema"]
        properties = set(schema.get("properties", {}))
        unknown = sorted(set(arguments) - properties)
        if unknown:
            return "Unknown tool arguments: " + ", ".join(unknown)
        missing = [name for name in schema.get("required", []) if name not in arguments]
        if missing:
            return "Missing required tool arguments: " + ", ".join(missing)
        return None

    @staticmethod
    def _json_body(response: HTTPResponse) -> Any:
        try:
            return sanitize_summary_payload(response.json())
        except Exception:
            return None

    def _success_data(self, tool_name: str, response: HTTPResponse) -> Any:
        if tool_name != "download_artifact":
            return self._json_body(response)
        disposition = str(response.headers.get("content-disposition") or "")
        return {
            "content_type": str(response.headers.get("content-type") or ""),
            "content_disposition": disposition,
            "size_bytes": len(response.content),
        }

    def _response_error(self, response: HTTPResponse) -> dict[str, Any]:
        body = self._json_body(response)
        if isinstance(body, dict):
            detail = body.get("detail", body.get("error", body))
        else:
            detail = "Local tool request failed."
        return sanitize_summary_payload({"code": "TOOL_HTTP_ERROR", "detail": detail})

    def _local_error(self, tool_name: str, code: str, message: str, status_code: int = 400) -> dict[str, Any]:
        return AgentToolResult(tool_name, False, status_code, None, error={"code": code, "message": message}).to_dict()

    @staticmethod
    def _workflow_result(
        task_id: str | None,
        steps: list[dict[str, Any]],
        summary: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        completed = bool(steps) and all(step.get("ok") for step in steps)
        summary_data = (summary or {}).get("data")
        artifact_data = (artifacts or {}).get("data")
        return sanitize_summary_payload({
            "simulation": "phase-8.3-local-agent",
            "completed": completed,
            "task_id": task_id,
            "steps": steps,
            "summary": summary_data,
            "artifacts": artifact_data,
            "reliability_information": (summary_data or {}).get("reliability_information") if isinstance(summary_data, dict) else None,
            "scientific_conclusion_generated": False,
        })
