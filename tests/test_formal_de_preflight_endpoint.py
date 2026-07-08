import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import formal_de_preflight
from backend.app.services.task_registry import reset_registry


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


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def _assert_no_forbidden_public_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_PUBLIC_FRAGMENTS)


def test_formal_de_preflight_endpoint_returns_completed_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        formal_de_preflight,
        "run_deseq2_preflight",
        lambda: {
            "r_available": True,
            "rscript_available": True,
            "r_version": "4.4.1",
            "rscript_version": "4.4.1",
            "biocmanager_available": True,
            "deseq2_available": True,
            "formal_method": "deseq2",
            "ready": True,
            "checked_at": "2026-07-09T00:00:00Z",
            "commands_checked": [
                "R --version",
                "Rscript --version",
                'Rscript --vanilla -e requireNamespace("BiocManager")',
                'Rscript --vanilla -e requireNamespace("DESeq2")',
            ],
            "warnings": [],
            "errors": [],
            "limitations": [
                "This preflight only checks local environment readiness for future DESeq2 execution.",
                "No DESeq2 differential expression analysis is run.",
                "No R or Bioconductor packages are installed, updated, or modified.",
            ],
        },
    )

    response = TestClient(app).get("/task/formal-de/preflight")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "formal_de_preflight_completed"
    assert body["formal_method"] == "deseq2"
    assert body["ready"] is True
    assert body["checks"]["r_available"] is True
    assert body["checks"]["rscript_available"] is True
    assert body["checks"]["biocmanager_available"] is True
    assert body["checks"]["deseq2_available"] is True
    assert body["checks"]["commands_checked"]
    assert body["limitations"]
    _assert_no_forbidden_public_fragments(body)


def test_formal_de_preflight_endpoint_missing_environment_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        formal_de_preflight,
        "check_executable_available",
        lambda name: False,
    )

    response = TestClient(app).get("/task/formal-de/preflight")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "formal_de_preflight_completed"
    assert isinstance(body["ready"], bool)
    assert body["ready"] is False
    assert body["checks"]["r_available"] is False
    assert body["checks"]["rscript_available"] is False
    assert body["errors"]
    assert body["limitations"]
    assert (
        "DESeq2 execution is not available until R, Rscript, BiocManager, and DESeq2 are installed."
        in body["limitations"]
    )
    _assert_no_forbidden_public_fragments(body)


def test_formal_de_preflight_endpoint_does_not_mutate_task_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        formal_de_preflight,
        "check_executable_available",
        lambda name: False,
    )
    client = TestClient(app)
    created = client.post("/task/create", json={}).json()

    response = client.get("/task/formal-de/preflight")
    status_response = client.get(f"/task/{created['task_id']}/status")

    assert response.status_code == 200
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "created"
    _assert_no_forbidden_public_fragments(response.json())
