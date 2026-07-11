import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_rate_limit_settings
from backend.app.main import app
from backend.app.services.task_registry import reset_registry


RATE_ENV = (
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW_SECONDS",
    "RATE_LIMIT_SCOPE",
    "RATE_LIMIT_EXEMPT_PATHS",
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch):
    for name in (
        *RATE_ENV,
        "BIOINFO_REQUIRE_API_KEY",
        "BIOINFO_API_KEY",
        "BIOINFO_API_KEY_HEADER",
        "BIOINFO_MAX_REQUEST_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_registry()
    yield
    reset_registry()


def _enable(monkeypatch: pytest.MonkeyPatch, requests: int = 2) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", str(requests))
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")


def test_defaults_are_safe_and_disabled() -> None:
    settings = get_rate_limit_settings()
    assert settings.enabled is False
    assert settings.requests == 60
    assert settings.window_seconds == 60
    assert settings.scope == "ip"
    assert settings.exempt_paths == ("/health", "/docs", "/openapi.json")


def test_disabled_by_default_does_not_limit_existing_route() -> None:
    client = TestClient(app)
    assert all(client.get("/system/r-env").status_code != 429 for _ in range(3))


def test_exempt_paths_are_not_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch, requests=1)
    client = TestClient(app)
    for path in ("/health", "/docs", "/openapi.json"):
        assert client.get(path).status_code == 200
        assert client.get(path).status_code == 200


def test_requests_below_limit_succeed_and_next_request_returns_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch, requests=2)
    client = TestClient(app)
    assert client.get("/system/r-env").status_code == 200
    assert client.get("/system/r-env").status_code == 200

    response = client.get("/system/r-env")
    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "rate_limit_exceeded",
            "message": "Too many requests. Please retry later.",
            "retry_after_seconds": 60,
        }
    }
    assert response.headers["retry-after"] == "60"


def test_rate_limit_and_api_key_auth_work_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch, requests=1)
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", "phase-7-4-key")
    client = TestClient(app)

    assert client.post("/task/create", json={}).status_code == 401
    headers = {"X-Bioinfo-API-Key": "phase-7-4-key"}
    assert client.post("/task/create", headers=headers, json={}).status_code == 200
    assert client.post("/task/create", headers=headers, json={}).status_code == 429


def test_request_size_middleware_still_rejects_accepted_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch, requests=3)
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", "10")
    response = TestClient(app).post("/task/create", json={"large": "x" * 100})
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "REQUEST_BODY_TOO_LARGE"


def test_existing_routes_remain_registered() -> None:
    client = TestClient(app)
    responses = (
        client.get("/health"),
        client.post("/projects", json={"name": "phase 7.4 route check"}),
        client.post("/coze/projects", json={"project_name": "phase 7.4 route check"}),
        client.get("/system/r-env"),
        client.get("/system/docker-r-env"),
        client.get("/ui"),
        client.post("/task/create", json={}),
    )
    assert all(response.status_code != 404 for response in responses)
