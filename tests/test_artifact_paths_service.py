import json
from pathlib import Path

import pytest

from backend.app.services.artifact_paths import (
    get_output_root,
    get_task_artifact_relative_path,
    get_task_output_dir,
    ensure_task_output_dir,
    list_placeholder_artifact_specs,
    resolve_task_artifact_path,
    validate_task_id_for_path,
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


def test_default_output_root_resolves_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOINFO_OUTPUT_ROOT", raising=False)

    output_root = get_output_root()

    assert output_root.is_absolute()
    assert output_root.parts[-2:] == ("data", "outputs")


def test_bioinfo_output_root_override_works(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _set_output_root(monkeypatch, tmp_path)

    assert get_output_root() == output_root.resolve()


def test_safe_task_id_returns_and_creates_task_output_dir_under_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _set_output_root(monkeypatch, tmp_path)

    output_dir = get_task_output_dir("task-abc_123")

    assert output_dir == (output_root / "tasks" / "task-abc_123").resolve()
    assert output_dir.exists() is False

    ensured_dir = ensure_task_output_dir("task-abc_123")

    assert ensured_dir == output_dir
    assert ensured_dir.is_dir()
    ensured_dir.relative_to(output_root.resolve())


@pytest.mark.parametrize("task_id", ["../task_0001", r"..\task_0001", ".."])
def test_unsafe_task_id_with_traversal_is_rejected(task_id: str) -> None:
    with pytest.raises(ValueError):
        validate_task_id_for_path(task_id)


@pytest.mark.parametrize("task_id", ["task/0001", r"task\0001"])
def test_unsafe_task_id_with_slash_or_backslash_is_rejected(task_id: str) -> None:
    with pytest.raises(ValueError, match="path separators"):
        validate_task_id_for_path(task_id)


def test_unsafe_task_id_with_colon_is_rejected() -> None:
    with pytest.raises(ValueError, match="colons"):
        validate_task_id_for_path("task:0001")


@pytest.mark.parametrize("task_id", ["", "   "])
def test_empty_task_id_is_rejected(task_id: str) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        validate_task_id_for_path(task_id)


def test_null_byte_task_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="null bytes"):
        validate_task_id_for_path("task_0001\x00")


def test_safe_artifact_filename_resolves_under_task_output_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _set_output_root(monkeypatch, tmp_path)

    artifact_path = resolve_task_artifact_path("task_0001", "run_summary.json")

    assert artifact_path == (output_root / "tasks" / "task_0001" / "run_summary.json").resolve()
    artifact_path.relative_to((output_root / "tasks" / "task_0001").resolve())
    assert get_task_artifact_relative_path("task_0001", "run_summary.json") == (
        "tasks/task_0001/run_summary.json"
    )


@pytest.mark.parametrize("filename", [r"C:\outputs\run_summary.json", "/mnt/run_summary.json"])
def test_absolute_artifact_filename_is_rejected(filename: str) -> None:
    with pytest.raises(ValueError, match="relative"):
        resolve_task_artifact_path("task_0001", filename)


@pytest.mark.parametrize("filename", ["../run_summary.json", r"..\run_summary.json"])
def test_traversal_artifact_filename_is_rejected(filename: str) -> None:
    with pytest.raises(ValueError):
        resolve_task_artifact_path("task_0001", filename)


def test_unsupported_artifact_suffix_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported artifact suffix"):
        resolve_task_artifact_path("task_0001", "run_summary.exe")


def test_placeholder_artifact_specs_use_safe_relative_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_output_root(monkeypatch, tmp_path)

    specs = list_placeholder_artifact_specs("task_demo")

    assert [spec["name"] for spec in specs] == [
        "run_summary.json",
        "qc_summary.json",
        "differential_expression_results.csv",
        "report.md",
    ]
    assert all(spec["relative_path"].startswith("tasks/task_demo/") for spec in specs)
    assert all(not Path(spec["relative_path"]).is_absolute() for spec in specs)
    assert all(spec["exists"] is False for spec in specs)
    assert all(spec["limitations"] for spec in specs)
    _assert_no_forbidden_fragments(specs)
