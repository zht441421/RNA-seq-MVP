import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


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
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "state" / "tasks.sqlite3"))
    reset_registry()
    yield input_root
    reset_registry()


def _assert_no_forbidden_fragments(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


def _create_task(client: TestClient) -> str:
    response = client.post("/task/create", json={})
    assert response.status_code == 200
    return response.json()["task_id"]


def _write_inputs(input_root: Path) -> tuple[str, str]:
    demo_dir = input_root / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / "metadata.csv").write_text(
        "\n".join(
            [
                "sample_id,condition",
                "sample_1,control",
                "sample_2,control",
                "sample_3,treatment",
                "sample_4,treatment",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (demo_dir / "counts.csv").write_text(
        "\n".join(
            [
                "gene_id,sample_1,sample_2,sample_3,sample_4",
                "GeneA,100,120,250,260",
                "GeneB,5,3,4,6",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return "demo/metadata.csv", "demo/counts.csv"


def _plan_payload(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _qc_payload(task_id: str, metadata_file: str, count_matrix_file: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "project_name": "demo_bulk_rnaseq",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "metadata_file": metadata_file,
        "count_matrix_file": count_matrix_file,
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast": "treatment_vs_control",
    }


def _run_payload(task_id: str) -> dict[str, object]:
    return {
        **_plan_payload(task_id),
        "execution_mode": "minimal_real",
    }


def _register(
    client: TestClient,
    task_id: str,
    input_role: str,
    source_relative_path: str,
):
    return client.post(
        f"/task/{task_id}/inputs/register",
        json={
            "input_role": input_role,
            "source_relative_path": source_relative_path,
        },
    )


def test_unknown_task_input_registration_returns_deterministic_404(
    isolated_task_env: Path,
) -> None:
    response = TestClient(app).post(
        "/task/task_missing/inputs/register",
        json={"input_role": "metadata", "source_relative_path": "demo/metadata.csv"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found."}
    _assert_no_forbidden_fragments(response.json())


def test_register_metadata_and_count_matrix_returns_safe_responses(
    isolated_task_env: Path,
) -> None:
    metadata_file, count_matrix_file = _write_inputs(isolated_task_env)
    client = TestClient(app)
    task_id = _create_task(client)

    metadata_response = _register(client, task_id, "metadata", metadata_file)
    count_response = _register(client, task_id, "count_matrix", count_matrix_file)

    assert metadata_response.status_code == 200
    assert count_response.status_code == 200
    metadata_body = metadata_response.json()
    count_body = count_response.json()
    assert metadata_body["safe_relative_path"] == metadata_file
    assert metadata_body["next_required_inputs"] == ["count_matrix"]
    assert count_body["safe_relative_path"] == count_matrix_file
    assert count_body["next_required_inputs"] == []
    assert len(metadata_body["checksum_sha256"]) == 64
    assert len(count_body["checksum_sha256"]) == 64
    summary_response = client.get(f"/task/{task_id}/coze-summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["registered_inputs"] == {
        "count_matrix": count_matrix_file,
        "metadata": metadata_file,
    }
    _assert_no_forbidden_fragments(
        {
            "metadata": metadata_body,
            "count": count_body,
            "summary": summary_response.json(),
        }
    )


def test_task_audit_records_input_registration_if_registered(
    isolated_task_env: Path,
) -> None:
    metadata_file, _ = _write_inputs(isolated_task_env)
    client = TestClient(app)
    task_id = _create_task(client)
    assert _register(client, task_id, "metadata", metadata_file).status_code == 200

    audit_response = client.get(f"/task/{task_id}/audit")

    assert audit_response.status_code == 200
    event_types = [event["event_type"] for event in audit_response.json()["events"]]
    assert "task_input_registered" in event_types
    _assert_no_forbidden_fragments(audit_response.json())


def test_registered_inputs_allow_task_run_without_explicit_paths(
    isolated_task_env: Path,
) -> None:
    metadata_file, count_matrix_file = _write_inputs(isolated_task_env)
    client = TestClient(app)
    task_id = _create_task(client)
    assert _register(client, task_id, "metadata", metadata_file).status_code == 200
    assert _register(client, task_id, "count_matrix", count_matrix_file).status_code == 200
    assert client.post("/task/plan", json=_plan_payload(task_id)).status_code == 200
    assert client.post(
        "/task/qc",
        json=_qc_payload(task_id, metadata_file, count_matrix_file),
    ).status_code == 200

    run_response = client.post("/task/run", json=_run_payload(task_id))

    assert run_response.status_code == 200
    body = run_response.json()
    assert body["status"] == "minimal_analysis_completed"
    artifact_names = [artifact["name"] for artifact in body["artifacts"]]
    assert "normalized_counts_cpm.csv" in artifact_names
    _assert_no_forbidden_fragments(body)


def test_only_one_registered_input_then_run_returns_deterministic_error(
    isolated_task_env: Path,
) -> None:
    metadata_file, _ = _write_inputs(isolated_task_env)
    client = TestClient(app)
    task_id = _create_task(client)
    assert _register(client, task_id, "metadata", metadata_file).status_code == 200

    run_response = client.post("/task/run", json=_run_payload(task_id))

    assert run_response.status_code == 400
    assert run_response.json() == {
        "detail": "Both metadata and count matrix inputs are required."
    }
    _assert_no_forbidden_fragments(run_response.json())


def test_unsafe_path_registration_is_rejected_safely(
    isolated_task_env: Path,
) -> None:
    client = TestClient(app)
    task_id = _create_task(client)

    response = _register(client, task_id, "metadata", "../metadata.csv")

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid input path."}
    _assert_no_forbidden_fragments(response.json())
