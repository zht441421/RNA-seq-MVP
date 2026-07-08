from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from backend.app.services.artifact_paths import (
    ALLOWED_PLACEHOLDER_ARTIFACT_SUFFIXES,
    get_output_root,
    list_deseq2_artifact_specs,
    list_dry_run_record_specs,
    list_minimal_rnaseq_artifact_specs,
    list_placeholder_artifact_specs,
    validate_task_id_for_path,
)
from backend.app.services.task_service import get_task, list_task_artifacts


_MEDIA_TYPES = {
    ".json": "application/json",
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".txt": "text/plain",
}
_GENERIC_NOT_FOUND = "Artifact not found."
_GENERIC_UNSAFE_NAME = "Unsafe artifact name."


@dataclass(frozen=True)
class ArtifactDownloadPayload:
    task_id: str
    artifact_name: str
    path: Path
    media_type: str
    filename: str


class ArtifactDownloadError(ValueError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class _ArtifactCandidate:
    artifact_name: str
    safe_relative_path: str


def validate_download_artifact_name(artifact_name: str) -> str:
    if not isinstance(artifact_name, str) or not artifact_name.strip():
        raise ArtifactDownloadError(400, _GENERIC_UNSAFE_NAME)

    safe_name = artifact_name.strip()
    if "\x00" in safe_name:
        raise ArtifactDownloadError(400, _GENERIC_UNSAFE_NAME)

    if _is_absolute_path(safe_name):
        raise ArtifactDownloadError(400, _GENERIC_UNSAFE_NAME)

    if "/" in safe_name or "\\" in safe_name:
        raise ArtifactDownloadError(400, _GENERIC_UNSAFE_NAME)

    if ":" in safe_name:
        raise ArtifactDownloadError(400, _GENERIC_UNSAFE_NAME)

    if _has_path_traversal(safe_name):
        raise ArtifactDownloadError(400, _GENERIC_UNSAFE_NAME)

    if safe_name.startswith("."):
        raise ArtifactDownloadError(400, _GENERIC_UNSAFE_NAME)

    suffix = PurePosixPath(safe_name).suffix.lower()
    if suffix not in ALLOWED_PLACEHOLDER_ARTIFACT_SUFFIXES:
        raise ArtifactDownloadError(400, _GENERIC_UNSAFE_NAME)

    return safe_name


def resolve_artifact_download_path(task_id: str, artifact_name: str) -> Path:
    safe_task_id = _validate_download_task_id(task_id)
    safe_name = validate_download_artifact_name(artifact_name)
    expected_relative_path = _task_artifact_relative_path(safe_task_id, safe_name)
    candidate = _find_known_artifact(safe_task_id, safe_name, expected_relative_path)

    output_root = get_output_root()
    artifact_path = _resolve_safe_relative_path(output_root, candidate.safe_relative_path)
    if not _is_relative_to(artifact_path, output_root):
        raise ArtifactDownloadError(404, _GENERIC_NOT_FOUND)

    task_output_dir = (output_root / "tasks" / safe_task_id).resolve(strict=False)
    if not _is_relative_to(artifact_path, task_output_dir):
        raise ArtifactDownloadError(404, _GENERIC_NOT_FOUND)

    if not artifact_path.is_file():
        raise ArtifactDownloadError(404, _GENERIC_NOT_FOUND)

    return artifact_path


def get_artifact_download_payload(task_id: str, artifact_name: str) -> ArtifactDownloadPayload:
    safe_task_id = _validate_download_task_id(task_id)
    safe_name = validate_download_artifact_name(artifact_name)
    path = resolve_artifact_download_path(safe_task_id, safe_name)
    return ArtifactDownloadPayload(
        task_id=safe_task_id,
        artifact_name=safe_name,
        path=path,
        media_type=media_type_for_artifact_name(safe_name),
        filename=safe_name,
    )


def media_type_for_artifact_name(artifact_name: str) -> str:
    suffix = PurePosixPath(artifact_name).suffix.lower()
    return _MEDIA_TYPES.get(suffix, "application/octet-stream")


def _validate_download_task_id(task_id: str) -> str:
    try:
        safe_task_id = validate_task_id_for_path(task_id)
    except ValueError as exc:
        raise ArtifactDownloadError(404, _GENERIC_NOT_FOUND) from exc

    if get_task(safe_task_id) is None:
        raise ArtifactDownloadError(404, _GENERIC_NOT_FOUND)

    return safe_task_id


def _find_known_artifact(
    task_id: str,
    artifact_name: str,
    expected_relative_path: str,
) -> _ArtifactCandidate:
    candidates = _artifact_candidates_for_task(task_id)
    for candidate in candidates:
        if candidate.artifact_name != artifact_name:
            continue
        safe_relative_path = _validate_safe_relative_path(candidate.safe_relative_path)
        if safe_relative_path == expected_relative_path:
            return _ArtifactCandidate(
                artifact_name=candidate.artifact_name,
                safe_relative_path=safe_relative_path,
            )

    raise ArtifactDownloadError(404, _GENERIC_NOT_FOUND)


def _artifact_candidates_for_task(task_id: str) -> list[_ArtifactCandidate]:
    persisted_artifacts = list_task_artifacts(task_id)
    if persisted_artifacts:
        return [
            _ArtifactCandidate(
                artifact_name=str(artifact.get("artifact_name") or ""),
                safe_relative_path=str(artifact.get("safe_relative_path") or ""),
            )
            for artifact in persisted_artifacts
        ]

    return [
        _ArtifactCandidate(
            artifact_name=str(artifact["name"]),
            safe_relative_path=str(artifact["relative_path"]),
        )
        for artifact in _planned_artifact_specs(task_id)
    ]


def _planned_artifact_specs(task_id: str) -> list[dict]:
    deseq2_artifacts = list_deseq2_artifact_specs(task_id)
    if any(
        artifact["name"] == "deseq2_results.csv" and artifact["exists"]
        for artifact in deseq2_artifacts
    ):
        return deseq2_artifacts

    minimal_artifacts = list_minimal_rnaseq_artifact_specs(task_id)
    if any(
        artifact["name"] == "normalized_counts_cpm.csv" and artifact["exists"]
        for artifact in minimal_artifacts
    ):
        return minimal_artifacts

    return [
        *list_placeholder_artifact_specs(task_id),
        *[
            artifact
            for artifact in list_dry_run_record_specs(task_id)
            if artifact["exists"]
        ],
    ]


def _task_artifact_relative_path(task_id: str, artifact_name: str) -> str:
    return PurePosixPath("tasks", task_id, artifact_name).as_posix()


def _validate_safe_relative_path(path_value: str) -> str:
    path_text = str(path_value or "").strip().replace("\\", "/")
    if not path_text:
        raise ArtifactDownloadError(404, _GENERIC_NOT_FOUND)

    posix_path = PurePosixPath(path_text)
    windows_path = PureWindowsPath(path_text)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    ):
        raise ArtifactDownloadError(404, _GENERIC_NOT_FOUND)

    return posix_path.as_posix()


def _resolve_safe_relative_path(output_root: Path, safe_relative_path: str) -> Path:
    relative_path = PurePosixPath(_validate_safe_relative_path(safe_relative_path))
    return (output_root / Path(*relative_path.parts)).resolve(strict=False)


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


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
