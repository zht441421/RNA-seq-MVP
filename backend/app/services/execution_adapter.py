import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from backend.app.models.task import TaskRecord
from backend.app.services.artifact_paths import (
    ensure_task_output_dir,
    get_output_root,
    list_dry_run_record_specs,
    list_minimal_rnaseq_artifact_specs,
    list_placeholder_artifact_specs,
    resolve_task_artifact_path,
)
from backend.app.services.input_validation import validate_rnaseq_input_files
from backend.app.services.rnaseq_minimal import (
    CountMatrix,
    compute_cpm,
    compute_library_sizes,
    compute_preliminary_log2fc,
    filter_low_expression,
    read_count_matrix,
    read_metadata,
    validate_count_matrix,
    validate_metadata,
    validate_sample_alignment,
    write_csv,
    write_json,
    write_markdown_report,
)


_PLACEHOLDER_TIMESTAMP = "2026-01-01T00:00:00Z"
_MINIMAL_LOW_COUNT_FILTER = 10
_MINIMAL_OUTPUT_FILES = [
    "run_manifest.json",
    "execution_summary.json",
    "qc_summary.json",
    "normalized_counts_cpm.csv",
    "differential_expression_results.csv",
    "report.md",
]
_PRELIMINARY_LOG2FC_FIELDNAMES = [
    "gene_id",
    "mean_cpm_group_1",
    "mean_cpm_group_2",
    "log2_fold_change",
    "total_count",
    "analysis_note",
]


@dataclass(frozen=True)
class ExecutionRequest:
    task_id: str
    project_name: str = "unspecified"
    omics_type: str = "unspecified"
    metadata_file: str | None = None
    count_matrix_file: str | None = None
    execution_mode: str = "dry_run"
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


class MinimalBulkRNASeqExecutor:
    name = "minimal_bulk_rnaseq_executor"
    mode = "minimal_real"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return run_minimal_bulk_rnaseq(request, executor_name=self.name)


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


def _minimal_generated_file_entries(task_id: str) -> list[dict]:
    return [
        {
            "name": spec["name"],
            "relative_path": spec["relative_path"],
            "artifact_type": spec["artifact_type"],
            "description": spec["description"],
        }
        for spec in list_minimal_rnaseq_artifact_specs(task_id)
        if spec["name"] in _MINIMAL_OUTPUT_FILES
    ]


def _minimal_limitations() -> list[str]:
    return [
        "This is a minimal Bulk RNA-seq MVP analysis.",
        "CPM normalization and preliminary log2 fold-change ranking were computed.",
        "No formal differential expression statistical test was performed.",
        "No p-values or adjusted p-values are reported.",
        "Results are not a substitute for DESeq2, edgeR, or limma.",
        (
            "No DESeq2, edgeR, limma, GSEA, GO/KEGG gene-set analysis, "
            "Snakemake, Nextflow, Docker, Rscript, external command, or Coze call was run."
        ),
        "No database persistence or durable audit storage was added.",
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


def run_minimal_bulk_rnaseq(
    request: ExecutionRequest,
    *,
    executor_name: str = "minimal_bulk_rnaseq_executor",
) -> ExecutionResult:
    if not request.metadata_file or not request.count_matrix_file:
        raise ValueError(
            "metadata_file and count_matrix_file are required for minimal_real execution."
        )

    path_validation = validate_rnaseq_input_files(
        metadata_file=request.metadata_file,
        count_matrix_file=request.count_matrix_file,
    )
    if not path_validation.valid:
        raise ValueError("Input file validation failed: " + "; ".join(path_validation.errors))
    if path_validation.metadata.resolved_path is None:
        raise ValueError("Input file validation failed: metadata_file could not be resolved.")
    if path_validation.count_matrix.resolved_path is None:
        raise ValueError("Input file validation failed: count_matrix_file could not be resolved.")

    metadata = read_metadata(path_validation.metadata.resolved_path)
    counts = read_count_matrix(path_validation.count_matrix.resolved_path)
    validation_results = [
        validate_metadata(metadata),
        validate_count_matrix(counts),
        validate_sample_alignment(metadata, counts),
    ]
    validation_errors = [
        error
        for validation_result in validation_results
        for error in validation_result.errors
    ]
    warnings = [
        warning
        for validation_result in validation_results
        for warning in validation_result.warnings
    ]
    if validation_errors:
        raise ValueError("Minimal RNA-seq input validation failed: " + "; ".join(validation_errors))

    output_dir = ensure_task_output_dir(request.task_id)
    output_dir_relative = output_dir.relative_to(get_output_root()).as_posix()
    generated_file_entries = _minimal_generated_file_entries(request.task_id)
    limitations = _minimal_limitations()

    library_sizes = compute_library_sizes(counts)
    cpm = compute_cpm(counts)
    filtered_cpm = filter_low_expression(cpm, min_total_count=_MINIMAL_LOW_COUNT_FILTER)
    condition_counts = _condition_counts(metadata)
    warnings.extend(_library_size_warnings(library_sizes))

    preliminary_rows: list[dict] = []
    if len(condition_counts) == 2:
        preliminary_rows = compute_preliminary_log2fc(filtered_cpm, metadata)
    else:
        warnings.append(
            "Preliminary log2 fold-change ranking was skipped because exactly two condition groups were not present."
        )

    qc_summary = {
        "task_id": request.task_id,
        "sample_count": len(counts.sample_ids),
        "gene_count": len(counts.gene_ids),
        "retained_gene_count_after_filtering": len(filtered_cpm.gene_ids),
        "condition_counts": condition_counts,
        "library_sizes": {
            sample_id: _json_number(library_size)
            for sample_id, library_size in library_sizes.items()
        },
        "min_total_count_filter": _MINIMAL_LOW_COUNT_FILTER,
        "warnings": warnings,
        "limitations": limitations,
    }
    execution_summary = {
        "task_id": request.task_id,
        "status": "minimal_analysis_completed",
        "executor_name": executor_name,
        "started_at": _PLACEHOLDER_TIMESTAMP,
        "finished_at": _PLACEHOLDER_TIMESTAMP,
        "duration_seconds": 0.0,
        "real_execution_performed": True,
        "external_tools_called": False,
        "statistical_test_performed": False,
        "generated_files": generated_file_entries,
        "warnings": warnings,
        "limitations": limitations,
    }
    run_manifest = {
        "task_id": request.task_id,
        "executor_name": executor_name,
        "execution_mode": "minimal_real",
        "omics_type": request.omics_type,
        "project_name": request.project_name,
        "metadata_file": request.metadata_file,
        "count_matrix_file": request.count_matrix_file,
        "output_dir_relative": output_dir_relative,
        "generated_files": generated_file_entries,
        "limitations": limitations,
    }
    report_payload = {
        "metadata_file": request.metadata_file,
        "count_matrix_file": request.count_matrix_file,
        "sample_count": len(counts.sample_ids),
        "gene_count": len(counts.gene_ids),
        "retained_gene_count_after_filtering": len(filtered_cpm.gene_ids),
        "min_total_count_filter": _MINIMAL_LOW_COUNT_FILTER,
        "limitations": limitations,
    }

    write_json(resolve_task_artifact_path(request.task_id, "run_manifest.json"), run_manifest)
    write_json(
        resolve_task_artifact_path(request.task_id, "execution_summary.json"),
        execution_summary,
    )
    write_json(resolve_task_artifact_path(request.task_id, "qc_summary.json"), qc_summary)
    write_csv(
        resolve_task_artifact_path(request.task_id, "normalized_counts_cpm.csv"),
        _matrix_rows(cpm),
        ["gene_id", *cpm.sample_ids],
    )
    write_csv(
        resolve_task_artifact_path(request.task_id, "differential_expression_results.csv"),
        preliminary_rows,
        _PRELIMINARY_LOG2FC_FIELDNAMES,
    )
    write_markdown_report(resolve_task_artifact_path(request.task_id, "report.md"), report_payload)

    messages = [
        "Minimal Bulk RNA-seq executor invoked.",
        f"Prepared task output directory: {output_dir_relative}.",
        "Read metadata and count matrix files from the configured input root.",
        "Generated CPM counts, basic QC metrics, and preliminary log2 fold-change ranking.",
        "No external tools were called.",
    ]

    return ExecutionResult(
        task_id=request.task_id,
        status="minimal_analysis_completed",
        executor_name=executor_name,
        started_at=_PLACEHOLDER_TIMESTAMP,
        finished_at=_PLACEHOLDER_TIMESTAMP,
        duration_seconds=0.0,
        planned_artifacts=[],
        messages=messages,
        warnings=warnings,
        limitations=limitations,
        generated_files=list_minimal_rnaseq_artifact_specs(request.task_id),
    )


def _condition_counts(metadata: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in metadata:
        condition = str(row.get("condition", "")).strip()
        if condition:
            counts[condition] = counts.get(condition, 0) + 1
    return counts


def _library_size_warnings(library_sizes: dict) -> list[str]:
    return [
        f"Sample {sample_id} has a zero library size; CPM values were set to 0 for that sample."
        for sample_id, library_size in library_sizes.items()
        if library_size == 0
    ]


def _matrix_rows(matrix: CountMatrix) -> list[dict]:
    return [
        {
            "gene_id": gene_id,
            **{
                sample_id: matrix.values[gene_id][sample_id]
                for sample_id in matrix.sample_ids
            },
        }
        for gene_id in matrix.gene_ids
    ]


def _json_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def get_executor(mode: str = "placeholder") -> ExecutorProtocol:
    if mode == "placeholder":
        return PlaceholderRNASeqExecutor()
    if mode == "minimal_real":
        return MinimalBulkRNASeqExecutor()
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


def execute_task_minimal_rnaseq(
    task_id: str,
    metadata_file: str,
    count_matrix_file: str,
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
        metadata_file=metadata_file,
        count_matrix_file=count_matrix_file,
        execution_mode="minimal_real",
        dry_run=False,
    )
    return get_executor("minimal_real").execute(request)
