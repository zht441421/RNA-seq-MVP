import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from backend.app.models.task import TaskRecord
from backend.app.services.artifact_paths import (
    ensure_task_output_dir,
    get_output_root,
    list_dry_run_record_specs,
    list_placeholder_artifact_specs,
    resolve_task_artifact_path,
)


_PLACEHOLDER_TIMESTAMP = "2026-01-01T00:00:00Z"


@dataclass(frozen=True)
class ExecutionRequest:
    task_id: str
    project_name: str = "unspecified"
    omics_type: str = "unspecified"
    metadata_file: str | None = None
    count_matrix_file: str | None = None
    output_dir_relative: str | None = None
    dry_run: bool = True


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    status: str
    executor_name: str
    started_at: str
    finished_at: str
    duration_seconds: float
    planned_artifacts: list[dict] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    generated_files: list[dict] = field(default_factory=list)


class ExecutorProtocol(Protocol):
    name: str

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...


class PlaceholderRNASeqExecutor:
    name = "placeholder_rnaseq_executor"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return run_placeholder_dry_run(request, executor_name=self.name)


def _dry_run_limitations() -> list[str]:
    return [
        "This is a dry-run execution contract only.",
        "No real RNA-seq analysis is performed by this executor.",
        (
            "No DESeq2, edgeR, limma, FastQC, MultiQC, workflow engine, "
            "container, R script, shell script, or Coze call is executed."
        ),
        (
            "No biological result files, report files, plots, or durable "
            "database records are generated."
        ),
        "Only task-scoped dry-run record files are written.",
    ]


def _generated_file_entries(task_id: str) -> list[dict]:
    return [
        {
            "name": spec["name"],
            "relative_path": spec["relative_path"],
            "artifact_type": spec["artifact_type"],
            "description": spec["description"],
        }
        for spec in list_dry_run_record_specs(task_id)
    ]


def build_dry_run_manifest(
    request: ExecutionRequest,
    *,
    executor_name: str,
    output_dir_relative: str,
    planned_artifacts: list[dict],
    generated_files: list[dict],
    limitations: list[str],
) -> dict:
    return {
        "task_id": request.task_id,
        "executor_name": executor_name,
        "execution_mode": "dry_run",
        "omics_type": request.omics_type,
        "project_name": request.project_name,
        "output_dir_relative": output_dir_relative,
        "planned_artifacts": planned_artifacts,
        "generated_files": generated_files,
        "limitations": limitations,
    }


def build_execution_summary(
    request: ExecutionRequest,
    *,
    messages: list[str],
    warnings: list[str],
    limitations: list[str],
) -> dict:
    return {
        "task_id": request.task_id,
        "status": "dry_run_completed",
        "started_at": _PLACEHOLDER_TIMESTAMP,
        "finished_at": _PLACEHOLDER_TIMESTAMP,
        "duration_seconds": 0.0,
        "messages": messages,
        "warnings": warnings,
        "limitations": limitations,
        "real_execution_performed": False,
    }


def build_planned_steps() -> dict:
    steps = [
        (
            "validate_inputs",
            "Validate inputs",
            "Future execution will validate task inputs before any analysis starts.",
        ),
        (
            "prepare_output_directory",
            "Prepare output directory",
            "Future execution will prepare the task-scoped output directory.",
        ),
        (
            "run_quality_control",
            "Run quality control",
            "Future execution will run quality-control checks after validation passes.",
        ),
        (
            "run_differential_expression",
            "Run differential expression",
            "Future execution will run differential expression only after real runner support exists.",
        ),
        (
            "generate_report",
            "Generate report",
            "Future execution will generate a report from real validated outputs.",
        ),
        (
            "collect_artifacts",
            "Collect artifacts",
            "Future execution will collect generated outputs under the task directory.",
        ),
    ]
    return {
        "execution_mode": "dry_run",
        "steps": [
            {
                "step_id": step_id,
                "name": name,
                "status": "planned_not_executed",
                "description": description,
                "external_tool_called": False,
            }
            for step_id, name, description in steps
        ],
    }


def write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_placeholder_dry_run(
    request: ExecutionRequest,
    *,
    executor_name: str = "placeholder_rnaseq_executor",
) -> ExecutionResult:
    output_dir = ensure_task_output_dir(request.task_id)
    output_dir_relative = output_dir.relative_to(get_output_root()).as_posix()
    planned_artifacts = list_placeholder_artifact_specs(request.task_id)
    generated_file_entries = _generated_file_entries(request.task_id)
    limitations = _dry_run_limitations()
    messages = [
        "Placeholder execution adapter invoked.",
        f"Prepared task output directory: {output_dir_relative}.",
        "Dry-run execution contract records were written.",
        "No external tools were called.",
    ]
    warnings = [
        "No real RNA-seq execution was performed.",
        "Dry-run records are not biological results.",
    ]

    payloads = {
        "run_manifest.json": build_dry_run_manifest(
            request,
            executor_name=executor_name,
            output_dir_relative=output_dir_relative,
            planned_artifacts=planned_artifacts,
            generated_files=generated_file_entries,
            limitations=limitations,
        ),
        "execution_summary.json": build_execution_summary(
            request,
            messages=messages,
            warnings=warnings,
            limitations=limitations,
        ),
        "planned_steps.json": build_planned_steps(),
    }

    for filename, payload in payloads.items():
        write_json_file(resolve_task_artifact_path(request.task_id, filename), payload)

    return ExecutionResult(
        task_id=request.task_id,
        status="dry_run_completed",
        executor_name=executor_name,
        started_at=_PLACEHOLDER_TIMESTAMP,
        finished_at=_PLACEHOLDER_TIMESTAMP,
        duration_seconds=0.0,
        planned_artifacts=planned_artifacts,
        messages=messages,
        warnings=warnings,
        limitations=limitations,
        generated_files=list_dry_run_record_specs(request.task_id),
    )


def get_executor(mode: str = "placeholder") -> ExecutorProtocol:
    if mode == "placeholder":
        return PlaceholderRNASeqExecutor()
    raise ValueError(f"Unsupported executor mode: {mode}")


def execute_task_placeholder(
    task_id: str,
    registry_record: TaskRecord | None = None,
    project_name: str | None = None,
    omics_type: str | None = None,
) -> ExecutionResult:
    request = ExecutionRequest(
        task_id=task_id,
        project_name=(
            project_name
            or (registry_record.project_name if registry_record is not None else "unspecified")
        ),
        omics_type=(
            omics_type
            or (registry_record.omics_type if registry_record is not None else "unspecified")
        ),
        dry_run=True,
    )
    return get_executor("placeholder").execute(request)
