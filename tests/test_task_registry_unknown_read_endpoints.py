import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


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


@pytest.fixture(autouse=True)
def isolated_registry():
    reset_registry()
    yield
    reset_registry()


def _assert_no_forbidden_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


@pytest.mark.parametrize(
    "path",
    [
        "/task/task_missing/report",
        "/task/task_missing/artifacts",
        "/task/task_missing/audit",
    ],
)
def test_unknown_task_id_read_endpoints_return_deterministic_404(path: str) -> None:
    response = TestClient(app).get(path)

    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "Task not found: task_missing"}
    assert "detail" in body
    _assert_no_forbidden_fragments(body)
