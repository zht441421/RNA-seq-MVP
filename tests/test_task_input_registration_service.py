import json
from pathlib import Path

import pytest

from backend.app.services.task_inputs import (
    TaskInputRegistrationError,
    register_task_input,
    validate_input_role,
    validate_source_relative_path,
)
from backend.app.services.task_registry import create_task, list_task_inputs, reset_registry


FORBIDDEN_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "traceback",
    "token",
    "password",
    "secret",
)


@pytest.fixture()
def isolated_task_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    input_root = tmp_path / "inputs"
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "state" / "tasks.sqlite3"))
    reset_registry()
    yield input_root
    reset_registry()


def _assert_no_forbidden_fragments(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


def _write_file(input_root: Path, relative_path: str, text: str = "a,b\n1,2\n") -> None:
    path = input_root / Path(*relative_path.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_input_roles_are_validated() -> None:
    assert validate_input_role("metadata") == "metadata"
    assert validate_input_role("count_matrix") == "count_matrix"

    for role in ("", "sample_sheet", "../metadata", r"metadata\bad"):
        with pytest.raises(TaskInputRegistrationError) as exc_info:
            validate_input_role(role)
        assert exc_info.value.status_code == 400
        _assert_no_forbidden_fragments({"detail": exc_info.value.detail})


def test_safe_relative_path_is_accepted(isolated_task_env: Path) -> None:
    _write_file(isolated_task_env, "deseq2_minimal/metadata.csv")

    assert validate_source_relative_path("deseq2_minimal/metadata.csv") == (
        "deseq2_minimal/metadata.csv"
    )


@pytest.mark.parametrize(
    "source_relative_path",
    [
        "../metadata.csv",
        r"..\metadata.csv",
        r"C:\temp\metadata.csv",
        r"D:\temp\metadata.csv",
        "/tmp/metadata.csv",
    ],
)
def test_unsafe_paths_are_rejected_safely(
    isolated_task_env: Path,
    source_relative_path: str,
) -> None:
    with pytest.raises(TaskInputRegistrationError) as exc_info:
        validate_source_relative_path(source_relative_path)

    assert exc_info.value.status_code == 400
    _assert_no_forbidden_fragments({"detail": exc_info.value.detail})


@pytest.mark.parametrize("source_relative_path", [".env", "pyproject.toml", "source.py"])
def test_unsupported_extensions_are_rejected_safely(
    isolated_task_env: Path,
    source_relative_path: str,
) -> None:
    _write_file(isolated_task_env, source_relative_path)

    with pytest.raises(TaskInputRegistrationError) as exc_info:
        validate_source_relative_path(source_relative_path)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Unsupported input file extension."
    _assert_no_forbidden_fragments({"detail": exc_info.value.detail})


def test_missing_file_is_rejected_safely(isolated_task_env: Path) -> None:
    with pytest.raises(TaskInputRegistrationError) as exc_info:
        validate_source_relative_path("missing/metadata.csv")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Input file not found."
    _assert_no_forbidden_fragments({"detail": exc_info.value.detail})


def test_registered_input_metadata_is_persisted(isolated_task_env: Path) -> None:
    _write_file(isolated_task_env, "demo/metadata.csv", "sample_id,condition\ns1,a\n")
    task = create_task()

    response = register_task_input(
        task_id=task.task_id,
        input_role="metadata",
        source_relative_path="demo/metadata.csv",
    )

    assert response["task_id"] == task.task_id
    assert response["input_role"] == "metadata"
    assert response["safe_relative_path"] == "demo/metadata.csv"
    assert response["registered"] is True
    assert response["next_required_inputs"] == ["count_matrix"]
    assert response["file_size_bytes"] is not None
    assert len(response["checksum_sha256"]) == 64

    persisted = list_task_inputs(task.task_id)
    assert len(persisted) == 1
    assert persisted[0]["input_role"] == "metadata"
    assert persisted[0]["safe_relative_path"] == "demo/metadata.csv"
    assert persisted[0]["checksum_sha256"] == response["checksum_sha256"]
    _assert_no_forbidden_fragments({"response": response, "persisted": persisted})
