import json
import sqlite3
from pathlib import Path

import pytest

from backend.app.models.task import TaskLifecycleEvent, TaskRecord, TaskStatus
from backend.app.services.task_store import TaskStore


FORBIDDEN_PUBLIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "token",
    "password",
    "secret",
)


def _task_record(task_id: str = "task_0001") -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=TaskStatus.CREATED,
        message="Task created.",
        task_type="bulk_rnaseq_placeholder",
        project_name="demo_bulk_rnaseq",
        omics_type="bulk_rnaseq",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        lifecycle_events=[
            TaskLifecycleEvent(
                event_type="task_created",
                message="Task record created in in-memory registry.",
                actor="system",
            )
        ],
        parameters={"project_name": "demo_bulk_rnaseq"},
    )


def _model_payload(model: object) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _assert_no_forbidden_public_fragments(value: object) -> None:
    text = json.dumps(value, sort_keys=True, default=str).lower()
    for forbidden_fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert forbidden_fragment not in text


def test_task_store_initializes_database(tmp_path: Path) -> None:
    db_path = tmp_path / "state" / "tasks.sqlite3"

    TaskStore(db_path)

    assert db_path.is_file()
    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"tasks", "task_events", "task_artifacts"}.issubset(table_names)


def test_task_store_creates_loads_updates_events_and_artifacts(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.sqlite3")
    store.save_task(_task_record())

    loaded = store.load_task("task_0001")
    assert loaded is not None
    assert loaded.task_id == "task_0001"
    assert loaded.status == TaskStatus.CREATED
    assert loaded.lifecycle_events[0].event_type == "task_created"

    updated = store.update_task_status(
        "task_0001",
        TaskStatus.PLANNED,
        event_type="plan_generated",
        message="Placeholder analysis plan generated and task status updated.",
        metadata={"next_status": "planned"},
    )
    assert updated is not None
    assert updated.status == TaskStatus.PLANNED
    assert updated.updated_at == "2026-01-01T00:00:01Z"

    events = store.list_lifecycle_events("task_0001")
    assert [event["event_type"] for event in events] == [
        "task_created",
        "plan_generated",
    ]
    assert events[1]["metadata"] == {"next_status": "planned"}

    store.save_artifact_metadata(
        task_id="task_0001",
        artifact_name="report.md",
        artifact_type="analysis_report",
        safe_relative_path="tasks/task_0001/report.md",
        description="Generated report.",
        metadata={"available": True},
    )
    artifacts = store.list_artifact_metadata("task_0001")
    assert artifacts == [
        {
            "artifact_name": "report.md",
            "artifact_type": "analysis_report",
            "safe_relative_path": "tasks/task_0001/report.md",
            "description": "Generated report.",
            "created_at": "2026-01-01T00:00:00Z",
            "metadata": {"available": True},
        }
    ]
    _assert_no_forbidden_public_fragments(
        {
            "task": _model_payload(updated),
            "events": events,
            "artifacts": artifacts,
        }
    )


def test_task_store_persists_across_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "tasks.sqlite3"
    first_store = TaskStore(db_path)
    first_store.save_task(_task_record())
    first_store.append_lifecycle_event(
        task_id="task_0001",
        event_type="qc_checked",
        message="Placeholder QC checks generated and task status updated.",
    )

    second_store = TaskStore(db_path)
    loaded = second_store.load_task("task_0001")

    assert loaded is not None
    assert loaded.task_id == "task_0001"
    assert [event.event_type for event in loaded.lifecycle_events] == [
        "task_created",
        "qc_checked",
    ]


def test_task_store_rejects_invalid_task_id_and_unsafe_artifact_path(
    tmp_path: Path,
) -> None:
    store = TaskStore(tmp_path / "tasks.sqlite3")

    with pytest.raises(ValueError, match="Invalid task_id"):
        store.save_task(_task_record("../task_0001"))

    store.save_task(_task_record())
    with pytest.raises(ValueError, match="safe relative path"):
        store.save_artifact_metadata(
            task_id="task_0001",
            artifact_name="report.md",
            safe_relative_path="D:\\secret\\report.md",
        )
