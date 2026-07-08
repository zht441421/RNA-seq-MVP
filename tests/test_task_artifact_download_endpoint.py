import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry, save_task_artifacts


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


def _assert_no_forbidden_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


def _create_task(client: TestClient) -> str:
    response = client.post("/task/create", json={})
    assert response.status_code == 200
    return response.json()["task_id"]


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


def test_task_artifact_download_returns_registered_report(
    isolated_task_env: Path,
) -> None:
    client = TestClient(app)
    task_id = _create_task(client)
    report_path = isolated_task_env / "tasks" / task_id / "report.md"
    report_path.parent.mkdir(parents=True)
    report_text = "# Downloadable report\n\nExpected report text.\n"
    report_path.write_text(report_text, encoding="utf-8")
    _register_artifact(task_id, "report.md", f"tasks/{task_id}/report.md")

    response = client.get(f"/task/{task_id}/artifacts/report.md/download")

    assert response.status_code == 200
    assert "Expected report text." in response.text
    assert response.headers["content-type"].startswith("text/markdown")
    content_disposition = response.headers["content-disposition"]
    assert "report.md" in content_disposition
    assert str(isolated_task_env).lower() not in content_disposition.lower()


def test_unknown_artifact_download_returns_deterministic_404(
    isolated_task_env: Path,
) -> None:
    client = TestClient(app)
    task_id = _create_task(client)

    response = client.get(f"/task/{task_id}/artifacts/not_registered.json/download")

    assert response.status_code == 404
    assert response.json() == {"detail": "Artifact not found."}
    _assert_no_forbidden_fragments(response.json())


def test_missing_registered_artifact_download_returns_safe_404(
    isolated_task_env: Path,
) -> None:
    client = TestClient(app)
    task_id = _create_task(client)
    _register_artifact(task_id, "qc_summary.json", f"tasks/{task_id}/qc_summary.json")

    response = client.get(f"/task/{task_id}/artifacts/qc_summary.json/download")

    assert response.status_code == 404
    assert response.json() == {"detail": "Artifact not found."}
    _assert_no_forbidden_fragments(response.json())


@pytest.mark.parametrize(
    "encoded_artifact_name",
    [
        "%2E%2E%2Freport.md",
        "%2E%2E%5Creport.md",
        "tasks%2Ftask_0001%2Freport.md",
        "C%3A%5Ctemp%5Creport.md",
    ],
)
def test_path_traversal_artifact_download_returns_safe_error(
    isolated_task_env: Path,
    encoded_artifact_name: str,
) -> None:
    client = TestClient(app)
    task_id = _create_task(client)

    response = client.get(
        f"/task/{task_id}/artifacts/{encoded_artifact_name}/download"
    )

    assert response.status_code in {400, 404}
    _assert_no_forbidden_fragments(response.json())


def test_unknown_task_download_returns_deterministic_404(
    isolated_task_env: Path,
) -> None:
    response = TestClient(app).get("/task/task_missing/artifacts/report.md/download")

    assert response.status_code == 404
    assert response.json() == {"detail": "Artifact not found."}
    _assert_no_forbidden_fragments(response.json())
