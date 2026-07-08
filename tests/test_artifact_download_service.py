import json
from pathlib import Path

import pytest

from backend.app.services import artifact_download
from backend.app.services.artifact_download import (
    ArtifactDownloadError,
    get_artifact_download_payload,
    media_type_for_artifact_name,
    resolve_artifact_download_path,
    validate_download_artifact_name,
)
from backend.app.services.task_registry import create_task, reset_registry, save_task_artifacts


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


@pytest.fixture()
def isolated_task_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "state" / "tasks.sqlite3"))
    reset_registry()
    yield output_root
    reset_registry()


def _assert_error_is_safe(exc: ArtifactDownloadError) -> None:
    body = {"detail": exc.detail}
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


def _register_artifact(task_id: str, artifact_name: str, relative_path: str) -> None:
    save_task_artifacts(
        task_id,
        [
            {
                "name": artifact_name,
                "artifact_type": "analysis_report",
                "path": relative_path,
                "description": "Generated artifact.",
                "available": True,
            }
        ],
    )


@pytest.mark.parametrize(
    "artifact_name",
    ["report.md", "deseq2_results.csv", "qc_summary.json"],
)
def test_validate_download_artifact_name_accepts_safe_names(artifact_name: str) -> None:
    assert validate_download_artifact_name(artifact_name) == artifact_name


@pytest.mark.parametrize(
    "artifact_name",
    [
        "../report.md",
        r"..\report.md",
        "tasks/task_0001/report.md",
        "/tmp/report.md",
        r"C:\temp\report.md",
        r"D:\temp\report.md",
        ".env",
        "task_store.sqlite3",
        "source.py",
    ],
)
def test_validate_download_artifact_name_rejects_unsafe_names(artifact_name: str) -> None:
    with pytest.raises(ArtifactDownloadError) as exc_info:
        validate_download_artifact_name(artifact_name)

    assert exc_info.value.status_code == 400
    _assert_error_is_safe(exc_info.value)


def test_resolves_task_scoped_artifact_under_output_root(isolated_task_env: Path) -> None:
    task = create_task()
    report_path = isolated_task_env / "tasks" / task.task_id / "report.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("# Safe report\n", encoding="utf-8")
    _register_artifact(task.task_id, "report.md", f"tasks/{task.task_id}/report.md")

    resolved_path = resolve_artifact_download_path(task.task_id, "report.md")

    assert resolved_path == report_path.resolve()
    resolved_path.relative_to(isolated_task_env.resolve())


def test_rejects_registered_path_for_another_task(isolated_task_env: Path) -> None:
    task = create_task()
    other_path = isolated_task_env / "tasks" / "task_9999" / "report.md"
    other_path.parent.mkdir(parents=True)
    other_path.write_text("# Wrong task\n", encoding="utf-8")
    _register_artifact(task.task_id, "report.md", "tasks/task_9999/report.md")

    with pytest.raises(ArtifactDownloadError) as exc_info:
        resolve_artifact_download_path(task.task_id, "report.md")

    assert exc_info.value.status_code == 404
    _assert_error_is_safe(exc_info.value)


def test_rejects_paths_outside_output_root_from_bad_metadata(
    isolated_task_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = create_task()
    monkeypatch.setattr(
        artifact_download,
        "list_task_artifacts",
        lambda task_id: [
            {
                "artifact_name": "report.md",
                "safe_relative_path": "../outside/report.md",
            }
        ],
    )

    with pytest.raises(ArtifactDownloadError) as exc_info:
        resolve_artifact_download_path(task.task_id, "report.md")

    assert exc_info.value.status_code == 404
    _assert_error_is_safe(exc_info.value)


def test_missing_file_is_handled_safely(isolated_task_env: Path) -> None:
    task = create_task()
    _register_artifact(task.task_id, "report.md", f"tasks/{task.task_id}/report.md")

    with pytest.raises(ArtifactDownloadError) as exc_info:
        get_artifact_download_payload(task.task_id, "report.md")

    assert exc_info.value.status_code == 404
    _assert_error_is_safe(exc_info.value)


def test_payload_uses_public_filename_and_media_type(isolated_task_env: Path) -> None:
    task = create_task()
    report_path = isolated_task_env / "tasks" / task.task_id / "report.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("# Safe report\n", encoding="utf-8")
    _register_artifact(task.task_id, "report.md", f"tasks/{task.task_id}/report.md")

    payload = get_artifact_download_payload(task.task_id, "report.md")

    assert payload.filename == "report.md"
    assert payload.media_type == "text/markdown"
    assert payload.path == report_path.resolve()
    assert media_type_for_artifact_name("plot.png") == "application/octet-stream"
