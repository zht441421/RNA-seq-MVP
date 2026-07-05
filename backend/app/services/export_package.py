import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.config import get_settings
from backend.app.utils.hashing import sha256_file


EXPORT_MANIFEST_NAME = "EXPORT_MANIFEST.json"
EXPORT_ZIP_SUFFIX = "_evidence_package.zip"
SKIP_DIR_NAMES = {".git", "__pycache__", ".pytest_cache"}
SKIP_FILE_SUFFIXES = {".pyc", ".pyo", ".tmp", ".temp", ".part"}


class ExportPackageError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


def create_export_package(project_id: str) -> Dict[str, Any]:
    settings = get_settings()
    artifact_root = settings.project_root / "artifacts" / project_id
    if not artifact_root.exists() or not artifact_root.is_dir():
        raise ExportPackageError(
            "ARTIFACT_DIR_NOT_FOUND",
            "No evidence package artifact directory exists for this project.",
            {"project_id": project_id, "artifact_dir": str(artifact_root)},
        )

    export_dir = settings.project_root / "exports" / project_id
    export_dir.mkdir(parents=True, exist_ok=True)
    export_zip_path = export_dir / f"{project_id}{EXPORT_ZIP_SUFFIX}"

    files, directories, excluded_files, warnings = _collect_export_entries(artifact_root, export_zip_path)
    created_at = _now_iso()
    manifest_payload = _build_export_manifest(
        project_id=project_id,
        created_at=created_at,
        artifact_root=artifact_root,
        export_zip_path=export_zip_path,
        included_files=files,
        excluded_files=excluded_files,
        warnings=warnings,
    )

    with zipfile.ZipFile(export_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in directories:
            archive.writestr(directory + "/", "")
        for file_info in files:
            archive.write(artifact_root / file_info["path"], file_info["path"])
        archive.writestr(EXPORT_MANIFEST_NAME, json.dumps(manifest_payload, indent=2, ensure_ascii=False))

    response = _export_response(
        project_id=project_id,
        status="created",
        export_zip_path=export_zip_path,
        created_at=created_at,
        included_file_count=len(files),
        warnings=warnings,
    )
    sidecar_payload = {**manifest_payload, "export_package_sha256": response["export_package_sha256"]}
    _write_sidecar_manifest(export_dir, sidecar_payload)
    return response


def get_export_package_metadata(project_id: str) -> Dict[str, Any]:
    settings = get_settings()
    export_dir = settings.project_root / "exports" / project_id
    export_zip_path = export_dir / f"{project_id}{EXPORT_ZIP_SUFFIX}"
    sidecar_path = export_dir / EXPORT_MANIFEST_NAME
    if not export_zip_path.exists():
        return {
            "project_id": project_id,
            "status": "not_created",
            "export_package_path": str(export_zip_path),
            "export_package_sha256": None,
            "size_bytes": None,
            "created_at": None,
            "included_file_count": 0,
            "warnings": ["Export package has not been generated for this project."],
        }

    created_at = None
    included_file_count = 0
    warnings: List[str] = []
    if sidecar_path.exists():
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            created_at = sidecar.get("created_at")
            included_file_count = len(sidecar.get("included_files") or [])
            warnings = sidecar.get("warnings") or []
        except Exception as exc:
            warnings.append(f"Could not read export sidecar manifest: {exc}")

    return _export_response(
        project_id=project_id,
        status="available",
        export_zip_path=export_zip_path,
        created_at=created_at or _mtime_iso(export_zip_path),
        included_file_count=included_file_count,
        warnings=warnings,
    )


def load_existing_export_metadata(project_id: str) -> Dict[str, Any]:
    metadata = get_export_package_metadata(project_id)
    return metadata if metadata["status"] != "not_created" else {}


def _collect_export_entries(
    artifact_root: Path,
    export_zip_path: Path,
) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]], List[str]]:
    files: List[Dict[str, Any]] = []
    directories: List[str] = []
    excluded_files: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for path in sorted(artifact_root.rglob("*")):
        relative_path = path.relative_to(artifact_root).as_posix()
        if _should_exclude(path, artifact_root, export_zip_path):
            if path.is_file():
                excluded_files.append({"path": relative_path, "reason": "cache, temporary, git, or export package file"})
            continue
        if path.is_dir():
            directories.append(relative_path)
            continue
        try:
            file_hash = sha256_file(path)
        except Exception as exc:
            file_hash = None
            warnings.append(f"Could not hash {relative_path}: {exc}")
        files.append(
            {
                "path": relative_path,
                "sha256": file_hash,
                "size_bytes": path.stat().st_size,
            }
        )
    return files, directories, excluded_files, warnings


def _should_exclude(path: Path, artifact_root: Path, export_zip_path: Path) -> bool:
    try:
        if path.resolve() == export_zip_path.resolve():
            return True
    except Exception:
        pass
    relative_parts = path.relative_to(artifact_root).parts
    if any(part in SKIP_DIR_NAMES for part in relative_parts):
        return True
    if path.is_file() and path.suffix.lower() in SKIP_FILE_SUFFIXES:
        return True
    return False


def _build_export_manifest(
    project_id: str,
    created_at: str,
    artifact_root: Path,
    export_zip_path: Path,
    included_files: List[Dict[str, Any]],
    excluded_files: List[Dict[str, Any]],
    warnings: List[str],
) -> Dict[str, Any]:
    run_status = _read_json(artifact_root / "09_environment" / "run_status.json")
    audit_log = _read_json(artifact_root / "10_audit_log.json")
    grade = (audit_log.get("reliability") or {}).get("grade")
    primary_method_status = run_status.get("primary_method_status") or (
        audit_log.get("run_status") or {}
    ).get("primary_method_status")
    strong_conclusion_allowed = grade in {"A", "B"} and primary_method_status != "completed_with_warning"
    return {
        "project_id": project_id,
        "created_at": created_at,
        "source_artifact_dir": str(artifact_root),
        "export_package_path": str(export_zip_path),
        "included_files": included_files,
        "excluded_files": excluded_files,
        "manifest_present": (artifact_root / "manifest.json").exists(),
        "reliability_grade": grade,
        "strong_conclusion_allowed": strong_conclusion_allowed,
        "primary_method_status": primary_method_status,
        "validation_consistency_score": _nullable_float(run_status.get("validation_consistency_score")),
        "warnings": warnings,
    }


def _export_response(
    project_id: str,
    status: str,
    export_zip_path: Path,
    created_at: Optional[str],
    included_file_count: int,
    warnings: List[str],
) -> Dict[str, Any]:
    sha256 = None
    size_bytes = None
    response_warnings = list(warnings)
    if export_zip_path.exists():
        try:
            sha256 = sha256_file(export_zip_path)
            size_bytes = export_zip_path.stat().st_size
        except Exception as exc:
            response_warnings.append(f"Could not hash export package: {exc}")
    return {
        "project_id": project_id,
        "status": status,
        "export_package_path": str(export_zip_path),
        "export_package_sha256": sha256,
        "size_bytes": size_bytes,
        "created_at": created_at,
        "included_file_count": included_file_count,
        "warnings": response_warnings,
    }


def _write_sidecar_manifest(export_dir: Path, payload: Dict[str, Any]) -> None:
    (export_dir / EXPORT_MANIFEST_NAME).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _nullable_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
