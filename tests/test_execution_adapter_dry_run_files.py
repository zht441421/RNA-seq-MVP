import json
from pathlib import Path

import pytest

from backend.app.services.artifact_paths import resolve_task_artifact_path
from backend.app.services.execution_adapter import (
    ExecutionRequest,
    build_dry_run_manifest,
    build_execution_summary,
    build_planned_steps,
    run_placeholder_dry_run,
)


def _set_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    return output_root


def test_dry_run_payload_builders_are_deterministic_in_structure() -> None:
    request = ExecutionRequest(
        task_id="task_demo",
        project_name="demo_bulk_rnaseq",
        omics_type="bulk_rnaseq",
    )
    planned_artifacts = [
        {
            "name": "run_summary.json",
            "relative_path": "tasks/task_demo/run_summary.json",
            "artifact_type": "run_summary",
            "exists": False,
        }
    ]
    generated_files = [
        {
            "name": "run_manifest.json",
            "relative_path": "tasks/task_demo/run_manifest.json",
            "artifact_type": "dry_run_manifest",
        }
    ]
    limitations = ["Dry-run contract only."]
    messages = ["Dry-run execution contract records were written."]
    warnings = ["No real RNA-seq execution was performed."]

    manifest = build_dry_run_manifest(
        request,
        executor_name="placeholder_rnaseq_executor",
        output_dir_relative="tasks/task_demo",
        planned_artifacts=planned_artifacts,
        generated_files=generated_files,
        limitations=limitations,
    )
    summary = build_execution_summary(
        request,
        messages=messages,
        warnings=warnings,
        limitations=limitations,
    )
    planned_steps = build_planned_steps()

    assert manifest == {
        "task_id": "task_demo",
        "executor_name": "placeholder_rnaseq_executor",
        "execution_mode": "dry_run",
        "omics_type": "bulk_rnaseq",
        "project_name": "demo_bulk_rnaseq",
        "output_dir_relative": "tasks/task_demo",
        "planned_artifacts": planned_artifacts,
        "generated_files": generated_files,
        "limitations": limitations,
    }
    assert summary == {
        "task_id": "task_demo",
        "status": "dry_run_completed",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:00Z",
        "duration_seconds": 0.0,
        "messages": messages,
        "warnings": warnings,
        "limitations": limitations,
        "real_execution_performed": False,
    }
    assert [step["step_id"] for step in planned_steps["steps"]] == [
        "validate_inputs",
        "prepare_output_directory",
        "run_quality_control",
        "run_differential_expression",
        "generate_report",
        "collect_artifacts",
    ]
    assert all(step["external_tool_called"] is False for step in planned_steps["steps"])


def test_run_placeholder_dry_run_writes_generated_files_under_output_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _set_output_root(monkeypatch, tmp_path)

    result = run_placeholder_dry_run(
        ExecutionRequest(
            task_id="task_demo",
            project_name="demo_bulk_rnaseq",
            omics_type="bulk_rnaseq",
        )
    )

    assert result.status == "dry_run_completed"
    assert [artifact["relative_path"] for artifact in result.generated_files] == [
        "tasks/task_demo/run_manifest.json",
        "tasks/task_demo/execution_summary.json",
        "tasks/task_demo/planned_steps.json",
    ]
    assert all(artifact["exists"] is True for artifact in result.generated_files)
    assert all(not Path(artifact["relative_path"]).is_absolute() for artifact in result.generated_files)

    for artifact in result.generated_files:
        path = resolve_task_artifact_path("task_demo", artifact["name"])
        assert path.is_file()
        path.relative_to(output_root / "tasks" / "task_demo")

    manifest_path = resolve_task_artifact_path("task_demo", "run_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["output_dir_relative"] == "tasks/task_demo"
    assert all(
        not Path(entry["relative_path"]).is_absolute()
        for entry in manifest["generated_files"]
    )


def test_run_placeholder_dry_run_rejects_unsafe_task_id_through_path_layer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _set_output_root(monkeypatch, tmp_path)

    with pytest.raises(ValueError):
        run_placeholder_dry_run(ExecutionRequest(task_id="../task_demo"))

    assert output_root.exists() is False
