import json
from dataclasses import asdict
from pathlib import Path

import pytest

from backend.app.services.execution_adapter import (
    ExecutionRequest,
    PlaceholderRNASeqExecutor,
    execute_task_placeholder,
    get_executor,
)


FORBIDDEN_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "token",
    "password",
    "secret",
)


def _set_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    return output_root


def _assert_no_forbidden_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


def test_placeholder_executor_returns_deterministic_execution_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _set_output_root(monkeypatch, tmp_path)
    request = ExecutionRequest(
        task_id="task_0001",
        project_name="demo_bulk_rnaseq",
        omics_type="bulk_rnaseq",
    )

    result = PlaceholderRNASeqExecutor().execute(request)

    assert result.task_id == "task_0001"
    assert result.status == "dry_run_completed"
    assert result.executor_name == "placeholder_rnaseq_executor"
    assert result.started_at == "2026-01-01T00:00:00Z"
    assert result.finished_at == "2026-01-01T00:00:00Z"
    assert result.duration_seconds == 0.0
    assert result.messages == [
        "Placeholder execution adapter invoked.",
        "Prepared task output directory: tasks/task_0001.",
        "Dry-run execution contract records were written.",
        "No external tools were called.",
    ]
    assert result.warnings == [
        "No real RNA-seq execution was performed.",
        "Dry-run records are not biological results.",
    ]
    assert any("No real RNA-seq analysis" in limitation for limitation in result.limitations)
    assert any("No DESeq2" in limitation for limitation in result.limitations)

    output_dir = output_root / "tasks" / "task_0001"
    assert output_dir.is_dir()
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "execution_summary.json",
        "planned_steps.json",
        "run_manifest.json",
    ]
    assert [artifact["relative_path"] for artifact in result.generated_files] == [
        "tasks/task_0001/run_manifest.json",
        "tasks/task_0001/execution_summary.json",
        "tasks/task_0001/planned_steps.json",
    ]
    assert all(artifact["exists"] is True for artifact in result.generated_files)


def test_placeholder_executor_returns_safe_planned_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_output_root(monkeypatch, tmp_path)

    result = PlaceholderRNASeqExecutor().execute(ExecutionRequest(task_id="task_demo"))

    assert [artifact["relative_path"] for artifact in result.planned_artifacts] == [
        "tasks/task_demo/run_summary.json",
        "tasks/task_demo/qc_summary.json",
        "tasks/task_demo/differential_expression_results.csv",
        "tasks/task_demo/report.md",
    ]
    assert all(artifact["exists"] is False for artifact in result.planned_artifacts)
    assert all(not Path(artifact["relative_path"]).is_absolute() for artifact in result.planned_artifacts)
    _assert_no_forbidden_fragments(asdict(result))


def test_execute_task_placeholder_uses_placeholder_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_output_root(monkeypatch, tmp_path)

    result = execute_task_placeholder("task_demo")

    assert result.executor_name == "placeholder_rnaseq_executor"
    assert result.status == "dry_run_completed"


def test_get_executor_returns_placeholder_executor() -> None:
    executor = get_executor("placeholder")

    assert executor.name == "placeholder_rnaseq_executor"


def test_get_executor_rejects_unsupported_mode_deterministically() -> None:
    with pytest.raises(ValueError, match="Unsupported executor mode: real_r"):
        get_executor("real_r")
