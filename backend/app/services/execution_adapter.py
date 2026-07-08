from dataclasses import dataclass, field
from typing import Protocol

from backend.app.models.task import TaskRecord
from backend.app.services.artifact_paths import (
    ensure_task_output_dir,
    get_output_root,
    list_placeholder_artifact_specs,
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


class ExecutorProtocol(Protocol):
    name: str

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...


class PlaceholderRNASeqExecutor:
    name = "placeholder_rnaseq_executor"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        output_dir = ensure_task_output_dir(request.task_id)
        output_dir_relative = output_dir.relative_to(get_output_root()).as_posix()
        planned_artifacts = list_placeholder_artifact_specs(request.task_id)

        return ExecutionResult(
            task_id=request.task_id,
            status="placeholder_execution_completed",
            executor_name=self.name,
            started_at=_PLACEHOLDER_TIMESTAMP,
            finished_at=_PLACEHOLDER_TIMESTAMP,
            duration_seconds=0.0,
            planned_artifacts=planned_artifacts,
            messages=[
                "Placeholder execution adapter invoked.",
                f"Prepared task output directory: {output_dir_relative}.",
                "Planned artifact paths were loaded from the artifact output contract.",
            ],
            warnings=[
                "No real RNA-seq execution was performed.",
            ],
            limitations=[
                "No real RNA-seq analysis is performed by this executor.",
                "No DESeq2, edgeR, limma, FastQC, MultiQC, enrichment analysis, Snakemake, Nextflow, Docker, Rscript, shell scripts, or Coze calls are executed.",
                "No biological result files, report files, logs, or durable database records are generated.",
                "Only the task-scoped output directory may be created.",
            ],
        )


def get_executor(mode: str = "placeholder") -> ExecutorProtocol:
    if mode == "placeholder":
        return PlaceholderRNASeqExecutor()
    raise ValueError(f"Unsupported executor mode: {mode}")


def execute_task_placeholder(
    task_id: str,
    registry_record: TaskRecord | None = None,
) -> ExecutionResult:
    request = ExecutionRequest(
        task_id=task_id,
        project_name=registry_record.project_name if registry_record is not None else "unspecified",
        omics_type=registry_record.omics_type if registry_record is not None else "unspecified",
        dry_run=True,
    )
    return get_executor("placeholder").execute(request)
