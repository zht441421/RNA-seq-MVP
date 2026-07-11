import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


EXPECTED_KEY = "phase-7-3-correct-key"
LIMIT = "180"
OVERSIZED_SECRET = "submitted-private-body-" * 30
UNSAFE = (
    OVERSIZED_SECRET,
    LIMIT,
    EXPECTED_KEY,
    "BIOINFO_MAX_REQUEST_BYTES",
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "traceback",
    "token=",
    "password=",
    "secret=",
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "BIOINFO_MAX_REQUEST_BYTES",
        "BIOINFO_REQUIRE_API_KEY",
        "BIOINFO_API_KEY",
        "BIOINFO_API_KEY_HEADER",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_registry()
    yield
    reset_registry()


def _assert_oversized(response) -> None:
    assert response.status_code == 413
    assert response.json() == {
        "detail": {
            "code": "REQUEST_BODY_TOO_LARGE",
            "message": "Request body exceeds the configured limit.",
        }
    }
    rendered = json.dumps(response.json()).lower()
    for fragment in UNSAFE:
        assert fragment.lower() not in rendered


def _large_post(client: TestClient, path: str, headers=None):
    return client.post(path, headers=headers, json={"payload": OVERSIZED_SECRET})


def test_default_mode_preserves_create_behavior() -> None:
    response = TestClient(app).post("/task/create", json={})
    assert response.status_code == 200
    assert "task_id" in response.json()


def test_small_create_succeeds_when_limit_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", LIMIT)
    response = TestClient(app).post("/task/create", json={})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "path",
    ["/task/create", "/task/run", "/task/example/inputs/register"],
)
def test_oversized_task_posts_return_sanitized_413(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", LIMIT)
    _assert_oversized(_large_post(TestClient(app), path))


def test_health_and_openapi_remain_accessible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", "1")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_auth_disabled_and_limit_enabled_work_together(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", LIMIT)
    assert TestClient(app).post("/task/create", json={}).status_code == 200


def test_auth_enabled_correct_key_allows_small_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", LIMIT)
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", EXPECTED_KEY)
    response = TestClient(app).post(
        "/task/create", headers={"X-Bioinfo-API-Key": EXPECTED_KEY}, json={}
    )
    assert response.status_code == 200


def test_authenticated_oversized_request_returns_413(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", LIMIT)
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", EXPECTED_KEY)
    response = _large_post(
        TestClient(app), "/task/create", {"X-Bioinfo-API-Key": EXPECTED_KEY}
    )
    _assert_oversized(response)


def test_auth_precedes_size_limit_for_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Protected requests authenticate before their body is size-checked."""
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", LIMIT)
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", EXPECTED_KEY)
    response = _large_post(TestClient(app), "/task/create")
    assert response.status_code == 401
    assert response.json() == {"detail": "Valid API key required"}
