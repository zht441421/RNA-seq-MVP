from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from backend.app.models.task import TaskLifecycleEvent, TaskRecord, TaskStatus
from backend.app.services.artifact_paths import validate_task_id_for_path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TASK_STORE_PATH = _REPO_ROOT / "data" / "state" / "tasks.sqlite3"
_TASK_NUMBER_RE = re.compile(r"^task_(\d+)$")


class TaskStore:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = _resolve_store_path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    analysis_method TEXT NULL,
                    formal_de_method TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    event_payload_json TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    artifact_name TEXT NOT NULL,
                    artifact_type TEXT NULL,
                    safe_relative_path TEXT NOT NULL,
                    description TEXT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
                    UNIQUE(task_id, artifact_name, safe_relative_path)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_inputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    input_role TEXT NOT NULL,
                    safe_relative_path TEXT NOT NULL,
                    original_filename TEXT NULL,
                    content_type TEXT NULL,
                    file_size_bytes INTEGER NULL,
                    checksum_sha256 TEXT NULL,
                    registered_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
                    UNIQUE(task_id, input_role)
                )
                """
            )
            connection.commit()

    def save_task(
        self,
        task: TaskRecord,
        *,
        analysis_method: str | None = None,
        formal_de_method: str | None = None,
    ) -> None:
        safe_task_id = _validate_task_id(task.task_id)
        metadata = {
            "message": task.message,
            "task_type": task.task_type,
            "project_name": task.project_name,
            "omics_type": task.omics_type,
            "parameters": _safe_json_object(task.parameters),
        }
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO tasks (
                    task_id,
                    status,
                    analysis_method,
                    formal_de_method,
                    created_at,
                    updated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status = excluded.status,
                    analysis_method = excluded.analysis_method,
                    formal_de_method = excluded.formal_de_method,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    safe_task_id,
                    task.status.value,
                    _safe_optional_text(analysis_method),
                    _safe_optional_text(formal_de_method),
                    task.created_at,
                    task.updated_at,
                    _to_json(metadata),
                ),
            )
            connection.execute("DELETE FROM task_events WHERE task_id = ?", (safe_task_id,))
            for index, event in enumerate(task.lifecycle_events):
                event_time = _event_time_for_index(task.created_at, index)
                connection.execute(
                    """
                    INSERT INTO task_events (
                        task_id,
                        event_type,
                        event_time,
                        event_payload_json
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        safe_task_id,
                        event.event_type,
                        event_time,
                        _to_json(_event_to_payload(event)),
                    ),
                )
            connection.commit()

    def load_task(self, task_id: str) -> TaskRecord | None:
        safe_task_id = _validate_task_id(task_id)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (safe_task_id,),
            ).fetchone()
            if row is None:
                return None
            event_rows = connection.execute(
                """
                SELECT event_type, event_time, event_payload_json
                FROM task_events
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (safe_task_id,),
            ).fetchall()

        metadata = _from_json(row["metadata_json"])
        events = [
            _event_from_payload(
                event_type=event_row["event_type"],
                payload_json=event_row["event_payload_json"],
            )
            for event_row in event_rows
        ]
        return TaskRecord(
            task_id=safe_task_id,
            status=TaskStatus(row["status"]),
            message=str(metadata.get("message") or ""),
            task_type=str(metadata.get("task_type") or "placeholder"),
            project_name=str(metadata.get("project_name") or "unspecified"),
            omics_type=str(metadata.get("omics_type") or "unspecified"),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            lifecycle_events=events,
            parameters=_safe_json_object(metadata.get("parameters", {})),
        )

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus | str,
        *,
        event_type: str,
        message: str,
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> TaskRecord | None:
        task = self.load_task(task_id)
        if task is None:
            return None
        next_status = TaskStatus(status)
        task.status = next_status
        task.message = message
        return self.append_lifecycle_event(
            task_id=task_id,
            event_type=event_type,
            message=message,
            actor=actor,
            metadata=metadata,
            status=next_status,
        )

    def append_lifecycle_event(
        self,
        *,
        task_id: str,
        event_type: str,
        message: str,
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
        status: TaskStatus | None = None,
    ) -> TaskRecord | None:
        task = self.load_task(task_id)
        if task is None:
            return None
        if status is not None:
            task.status = status
            task.message = message
        task.lifecycle_events.append(
            TaskLifecycleEvent(
                event_type=event_type,
                message=message,
                actor=actor,
                metadata=metadata or {},
            )
        )
        task.updated_at = _event_time_for_index(
            task.created_at,
            len(task.lifecycle_events) - 1,
        )
        self.save_task(task)
        return task

    def list_lifecycle_events(self, task_id: str) -> list[dict[str, Any]]:
        safe_task_id = _validate_task_id(task_id)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT event_type, event_time, event_payload_json
                FROM task_events
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (safe_task_id,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            payload = _from_json(row["event_payload_json"])
            events.append(
                {
                    "event_type": row["event_type"],
                    "event_time": row["event_time"],
                    "message": str(payload.get("message") or ""),
                    "actor": str(payload.get("actor") or "system"),
                    "metadata": _safe_json_object(payload.get("metadata", {})),
                }
            )
        return events

    def save_artifact_metadata(
        self,
        *,
        task_id: str,
        artifact_name: str,
        safe_relative_path: str,
        artifact_type: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> None:
        safe_task_id = _validate_task_id(task_id)
        safe_path = _validate_safe_relative_path(safe_relative_path)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_artifacts (
                    task_id,
                    artifact_name,
                    artifact_type,
                    safe_relative_path,
                    description,
                    created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, artifact_name, safe_relative_path) DO UPDATE SET
                    artifact_type = excluded.artifact_type,
                    description = excluded.description,
                    created_at = excluded.created_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    safe_task_id,
                    _safe_required_text(artifact_name, "artifact_name"),
                    _safe_optional_text(artifact_type),
                    safe_path,
                    _safe_optional_text(description),
                    created_at or _created_at_for_artifact(safe_task_id),
                    _to_json(_safe_json_object(metadata or {})),
                ),
            )
            connection.commit()

    def replace_task_artifacts(
        self,
        task_id: str,
        artifacts: list[dict[str, Any]],
    ) -> None:
        safe_task_id = _validate_task_id(task_id)
        with self._connect() as connection:
            connection.execute("DELETE FROM task_artifacts WHERE task_id = ?", (safe_task_id,))
            connection.commit()
        for artifact in artifacts:
            path = artifact.get("path") or artifact.get("safe_relative_path") or artifact.get("relative_path")
            self.save_artifact_metadata(
                task_id=safe_task_id,
                artifact_name=str(artifact.get("name") or ""),
                artifact_type=_safe_optional_text(artifact.get("artifact_type")),
                safe_relative_path=str(path or ""),
                description=_safe_optional_text(artifact.get("description")),
                metadata={
                    key: value
                    for key, value in artifact.items()
                    if key not in {"name", "artifact_type", "path", "safe_relative_path", "relative_path", "description"}
                },
            )

    def list_artifact_metadata(self, task_id: str) -> list[dict[str, Any]]:
        safe_task_id = _validate_task_id(task_id)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    artifact_name,
                    artifact_type,
                    safe_relative_path,
                    description,
                    created_at,
                    metadata_json
                FROM task_artifacts
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (safe_task_id,),
            ).fetchall()
        return [
            {
                "artifact_name": row["artifact_name"],
                "artifact_type": row["artifact_type"],
                "safe_relative_path": row["safe_relative_path"],
                "description": row["description"],
                "created_at": row["created_at"],
                "metadata": _safe_json_object(_from_json(row["metadata_json"])),
            }
            for row in rows
        ]

    def save_task_input_metadata(
        self,
        *,
        task_id: str,
        input_role: str,
        safe_relative_path: str,
        original_filename: str | None = None,
        content_type: str | None = None,
        file_size_bytes: int | None = None,
        checksum_sha256: str | None = None,
        metadata: dict[str, Any] | None = None,
        registered_at: str | None = None,
    ) -> None:
        safe_task_id = _validate_task_id(task_id)
        safe_role = _validate_input_role(input_role)
        safe_path = _validate_safe_relative_path(safe_relative_path)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_inputs (
                    task_id,
                    input_role,
                    safe_relative_path,
                    original_filename,
                    content_type,
                    file_size_bytes,
                    checksum_sha256,
                    registered_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, input_role) DO UPDATE SET
                    safe_relative_path = excluded.safe_relative_path,
                    original_filename = excluded.original_filename,
                    content_type = excluded.content_type,
                    file_size_bytes = excluded.file_size_bytes,
                    checksum_sha256 = excluded.checksum_sha256,
                    registered_at = excluded.registered_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    safe_task_id,
                    safe_role,
                    safe_path,
                    _safe_optional_text(original_filename),
                    _safe_optional_text(content_type),
                    file_size_bytes,
                    _safe_optional_text(checksum_sha256),
                    registered_at or _created_at_for_artifact(safe_task_id),
                    _to_json(_safe_json_object(metadata or {})),
                ),
            )
            connection.commit()

    def list_task_input_metadata(self, task_id: str) -> list[dict[str, Any]]:
        safe_task_id = _validate_task_id(task_id)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    input_role,
                    safe_relative_path,
                    original_filename,
                    content_type,
                    file_size_bytes,
                    checksum_sha256,
                    registered_at,
                    metadata_json
                FROM task_inputs
                WHERE task_id = ?
                ORDER BY input_role ASC
                """,
                (safe_task_id,),
            ).fetchall()
        return [
            {
                "input_role": row["input_role"],
                "safe_relative_path": row["safe_relative_path"],
                "original_filename": row["original_filename"],
                "content_type": row["content_type"],
                "file_size_bytes": row["file_size_bytes"],
                "checksum_sha256": row["checksum_sha256"],
                "registered_at": row["registered_at"],
                "metadata": _safe_json_object(_from_json(row["metadata_json"])),
            }
            for row in rows
        ]

    def next_task_number(self) -> int:
        with self._connect() as connection:
            rows = connection.execute("SELECT task_id FROM tasks").fetchall()
        max_number = 0
        for (task_id,) in rows:
            match = _TASK_NUMBER_RE.fullmatch(str(task_id))
            if match:
                max_number = max(max_number, int(match.group(1)))
        return max_number + 1

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM task_inputs")
            connection.execute("DELETE FROM task_artifacts")
            connection.execute("DELETE FROM task_events")
            connection.execute("DELETE FROM tasks")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def get_task_store_path() -> Path:
    return _resolve_store_path(None)


def get_task_store() -> TaskStore:
    return TaskStore(get_task_store_path())


def _resolve_store_path(db_path: Path | str | None) -> Path:
    configured = db_path if db_path is not None else os.environ.get("BIOINFO_TASK_STORE_PATH", "")
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    return _DEFAULT_TASK_STORE_PATH.resolve(strict=False)


def _validate_task_id(task_id: str) -> str:
    try:
        return validate_task_id_for_path(task_id)
    except ValueError as exc:
        raise ValueError("Invalid task_id for task store.") from exc


def _validate_input_role(input_role: str) -> str:
    role = _safe_required_text(input_role, "input_role")
    if role not in {"metadata", "count_matrix"}:
        raise ValueError("Invalid task input role.")
    return role


def _validate_safe_relative_path(path_value: str) -> str:
    path_text = _safe_required_text(path_value, "safe_relative_path").replace("\\", "/")
    posix_path = PurePosixPath(path_text)
    windows_path = PureWindowsPath(path_text)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    ):
        raise ValueError("Artifact path must be a safe relative path.")
    return posix_path.as_posix()


def _safe_required_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return text


def _safe_optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _safe_json_object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _event_to_payload(event: TaskLifecycleEvent) -> dict[str, Any]:
    return {
        "message": event.message,
        "actor": event.actor,
        "metadata": _safe_json_object(event.metadata),
    }


def _event_from_payload(*, event_type: str, payload_json: str) -> TaskLifecycleEvent:
    payload = _from_json(payload_json)
    return TaskLifecycleEvent(
        event_type=str(event_type or ""),
        message=str(payload.get("message") or ""),
        actor=str(payload.get("actor") or "system"),
        metadata=_safe_json_object(payload.get("metadata", {})),
    )


def _to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _from_json(payload: str) -> dict[str, Any]:
    try:
        value = json.loads(payload or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _event_time_for_index(created_at: str, index: int) -> str:
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    timestamp = created + timedelta(seconds=index)
    return timestamp.isoformat().replace("+00:00", "Z")


def _created_at_for_artifact(task_id: str) -> str:
    match = _TASK_NUMBER_RE.fullmatch(task_id)
    task_number = int(match.group(1)) if match else 1
    base = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    timestamp = base + timedelta(seconds=task_number - 1)
    return timestamp.isoformat().replace("+00:00", "Z")
