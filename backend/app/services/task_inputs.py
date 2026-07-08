from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from backend.app.services.input_validation import (
    ALLOWED_RNASEQ_INPUT_SUFFIXES,
    validate_input_file,
)
from backend.app.services.task_service import (
    append_lifecycle_event,
    get_task,
    list_task_inputs,
    save_task_input,
)


SUPPORTED_INPUT_ROLES = {"metadata", "count_matrix"}
REQUIRED_INPUT_ROLES = ("metadata", "count_matrix")
_GENERIC_TASK_NOT_FOUND = "Task not found."
_BOTH_INPUTS_REQUIRED = "Both metadata and count matrix inputs are required."


class TaskInputRegistrationError(ValueError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def validate_input_role(input_role: str) -> str:
    if not isinstance(input_role, str) or not input_role.strip():
        raise TaskInputRegistrationError(400, "Unsupported input role.")

    role = input_role.strip()
    if (
        "/" in role
        or "\\" in role
        or ":" in role
        or _has_path_traversal(role)
        or _is_absolute_path(role)
        or role not in SUPPORTED_INPUT_ROLES
    ):
        raise TaskInputRegistrationError(400, "Unsupported input role.")

    return role


def validate_source_relative_path(source_relative_path: str) -> str:
    if not isinstance(source_relative_path, str) or not source_relative_path.strip():
        raise TaskInputRegistrationError(400, "Invalid input path.")

    path_text = source_relative_path.strip().replace("\\", "/")
    if "\x00" in path_text:
        raise TaskInputRegistrationError(400, "Invalid input path.")
    if _is_absolute_path(path_text):
        raise TaskInputRegistrationError(400, "Invalid input path.")
    if _has_path_traversal(path_text):
        raise TaskInputRegistrationError(400, "Invalid input path.")

    normalized_path = PurePosixPath(path_text).as_posix()
    validation = validate_input_file(
        normalized_path,
        allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES,
    )
    if validation.suffix not in ALLOWED_RNASEQ_INPUT_SUFFIXES:
        raise TaskInputRegistrationError(400, "Unsupported input file extension.")
    if not validation.valid:
        if any("File does not exist" in error for error in validation.errors):
            raise TaskInputRegistrationError(404, "Input file not found.")
        raise TaskInputRegistrationError(400, "Invalid input path.")

    return normalized_path


def register_task_input(
    *,
    task_id: str,
    input_role: str,
    source_relative_path: str,
) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise TaskInputRegistrationError(404, _GENERIC_TASK_NOT_FOUND)

    safe_role = validate_input_role(input_role)
    safe_relative_path = validate_source_relative_path(source_relative_path)
    validation = validate_input_file(
        safe_relative_path,
        allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES,
    )
    if validation.resolved_path is None or not validation.resolved_path.is_file():
        raise TaskInputRegistrationError(404, "Input file not found.")

    file_size_bytes = validation.resolved_path.stat().st_size
    checksum_sha256 = _sha256(validation.resolved_path)
    original_filename = PurePosixPath(safe_relative_path).name
    save_task_input(
        task.task_id,
        input_role=safe_role,
        safe_relative_path=safe_relative_path,
        original_filename=original_filename,
        content_type=None,
        file_size_bytes=file_size_bytes,
        checksum_sha256=checksum_sha256,
        metadata={"source": "register"},
    )
    append_lifecycle_event(
        task_id=task.task_id,
        event_type="task_input_registered",
        message=f"Task input registered for role {safe_role}.",
        metadata={
            "input_role": safe_role,
            "safe_relative_path": safe_relative_path,
        },
    )

    registered_inputs = registered_inputs_by_role(task.task_id)
    return {
        "task_id": task.task_id,
        "input_role": safe_role,
        "safe_relative_path": safe_relative_path,
        "registered": True,
        "warnings": [],
        "next_required_inputs": _next_required_inputs(registered_inputs),
        "file_size_bytes": file_size_bytes,
        "checksum_sha256": checksum_sha256,
    }


def registered_inputs_by_role(task_id: str) -> dict[str, dict[str, Any]]:
    return {
        str(input_metadata.get("input_role")): dict(input_metadata)
        for input_metadata in list_task_inputs(task_id)
        if str(input_metadata.get("input_role")) in SUPPORTED_INPUT_ROLES
    }


def registered_input_paths_for_run(task_id: str) -> tuple[str | None, str | None]:
    registered_inputs = registered_inputs_by_role(task_id)
    metadata = registered_inputs.get("metadata")
    count_matrix = registered_inputs.get("count_matrix")
    return (
        str(metadata.get("safe_relative_path")) if metadata else None,
        str(count_matrix.get("safe_relative_path")) if count_matrix else None,
    )


def require_complete_registered_inputs(task_id: str) -> tuple[str, str]:
    metadata_file, count_matrix_file = registered_input_paths_for_run(task_id)
    if not metadata_file or not count_matrix_file:
        raise TaskInputRegistrationError(400, _BOTH_INPUTS_REQUIRED)
    return metadata_file, count_matrix_file


def safe_registered_inputs_summary(task_id: str) -> dict[str, str]:
    return {
        role: str(metadata.get("safe_relative_path") or "")
        for role, metadata in registered_inputs_by_role(task_id).items()
        if metadata.get("safe_relative_path")
    }


def _next_required_inputs(registered_inputs: dict[str, dict[str, Any]]) -> list[str]:
    return [
        role
        for role in REQUIRED_INPUT_ROLES
        if role not in registered_inputs
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_absolute_path(path_value: str) -> bool:
    posix_path = PurePosixPath(path_value.replace("\\", "/"))
    windows_path = PureWindowsPath(path_value)
    return bool(
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or Path(path_value).is_absolute()
    )


def _has_path_traversal(path_value: str) -> bool:
    posix_path = PurePosixPath(path_value.replace("\\", "/"))
    windows_path = PureWindowsPath(path_value)
    return ".." in posix_path.parts or ".." in windows_path.parts
