from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Any
from uuid import uuid4

from backend.app.utils.logging import request_id_context


ANALYSIS_VERSION = "phase-7.6"
RUNNER_VERSION = "execution-trace-v1"


@dataclass
class ExecutionTrace:
    trace_id: str
    request_id: str | None
    task_id: str
    operation: str
    execution_start_timestamp: str
    execution_end_timestamp: str | None
    duration_seconds: float | None
    execution_status: str
    analysis_version: str
    runner_version: str
    configuration_snapshot_id: str
    runtime_metadata: dict[str, str]
    failure_reason: str | None = None
    _started_monotonic: float = 0.0


_TRACES: dict[str, list[ExecutionTrace]] = {}


def begin_execution_trace(
    task_id: str,
    operation: str,
    configuration: dict[str, Any] | None = None,
) -> ExecutionTrace:
    trace = ExecutionTrace(
        trace_id=uuid4().hex,
        request_id=request_id_context.get(),
        task_id=task_id,
        operation=operation,
        execution_start_timestamp=_utc_now(),
        execution_end_timestamp=None,
        duration_seconds=None,
        execution_status="started",
        analysis_version=ANALYSIS_VERSION,
        runner_version=RUNNER_VERSION,
        configuration_snapshot_id=_configuration_snapshot_id(configuration or {}),
        runtime_metadata={"runtime": "python", "metadata_status": "placeholder"},
        _started_monotonic=time.perf_counter(),
    )
    _TRACES.setdefault(task_id, []).append(trace)
    return trace


def complete_execution_trace(trace: ExecutionTrace) -> ExecutionTrace:
    return _finish(trace, "completed", None)


def fail_execution_trace(trace: ExecutionTrace, sanitized_reason: str) -> ExecutionTrace:
    return _finish(trace, "failed", _sanitize_reason(sanitized_reason))


def trace_metadata(trace: ExecutionTrace) -> dict[str, Any]:
    payload = asdict(trace)
    payload.pop("_started_monotonic", None)
    return payload


def list_execution_traces(task_id: str) -> list[dict[str, Any]]:
    return [trace_metadata(trace) for trace in _TRACES.get(task_id, ())]


def reset_execution_traces() -> None:
    _TRACES.clear()


def _finish(trace: ExecutionTrace, status: str, failure_reason: str | None) -> ExecutionTrace:
    trace.execution_end_timestamp = _utc_now()
    trace.duration_seconds = round(max(0.0, time.perf_counter() - trace._started_monotonic), 6)
    trace.execution_status = status
    trace.failure_reason = failure_reason
    return trace


def _configuration_snapshot_id(configuration: dict[str, Any]) -> str:
    rendered = json.dumps(configuration, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _sanitize_reason(reason: str) -> str:
    allowed = {
        "input_validation_failed",
        "contrast_validation_failed",
        "execution_failed",
        "formal_execution_failed",
    }
    return reason if reason in allowed else "execution_failed"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
