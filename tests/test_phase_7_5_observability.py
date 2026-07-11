import json
import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.middleware.observability import RequestObservabilityMiddleware
from backend.app.services.task_registry import reset_registry
from backend.app.utils.logging import StructuredJSONFormatter


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "BIOINFO_REQUIRE_API_KEY",
        "BIOINFO_API_KEY",
        "BIOINFO_API_KEY_HEADER",
        "BIOINFO_MAX_REQUEST_BYTES",
        "RATE_LIMIT_ENABLED",
        "RATE_LIMIT_REQUESTS",
        "RATE_LIMIT_WINDOW_SECONDS",
        "RATE_LIMIT_SCOPE",
        "RATE_LIMIT_EXEMPT_PATHS",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_registry()
    yield
    reset_registry()


def test_request_id_is_generated_returned_and_unique() -> None:
    client = TestClient(app)
    first = client.get("/health").headers["x-request-id"]
    second = client.get("/health").headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert re.fullmatch(r"[0-9a-f]{32}", second)
    assert first != second


def test_health_response_is_backward_compatible() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "bioinformatics-agent-backend",
        "version": "0.2.0",
        "phase": "phase-2-api-skeleton",
    }


def test_structured_formatter_includes_operational_fields() -> None:
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "request_completed", (), None
    )
    record.request_id = "request-1"
    record.route = "/health"
    record.status_code = 200
    rendered = json.loads(StructuredJSONFormatter().format(record))
    assert rendered["timestamp"]
    assert rendered["level"] == "INFO"
    assert rendered["service"] == "bioinformatics-agent-backend"
    assert rendered["request_id"] == "request-1"
    assert rendered["route"] == "/health"
    assert rendered["status_code"] == 200


def test_unhandled_errors_are_sanitized_and_correlated() -> None:
    failing_app = FastAPI()

    @failing_app.get("/failure")
    def failure():
        raise RuntimeError("private traceback detail")

    failing_app.add_middleware(RequestObservabilityMiddleware)
    response = TestClient(failing_app, raise_server_exceptions=False).get("/failure")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["x-request-id"]
    assert "private traceback detail" not in response.text
    assert "traceback" not in response.text.lower()


def test_api_key_middleware_still_precedes_protected_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", "phase-7-5-key")
    response = TestClient(app).post("/task/create", json={})
    assert response.status_code == 401
    assert response.json() == {"detail": "Valid API key required"}
    assert response.headers["x-request-id"]


def test_rate_limiting_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "7")
    client = TestClient(app)
    for _ in range(7):
        assert client.get("/system/r-env").status_code == 200
    response = client.get("/system/r-env")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limit_exceeded"
    assert response.headers["x-request-id"]


def test_request_size_limiting_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", "10")
    response = TestClient(app).post("/task/create", json={"value": "x" * 100})
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "REQUEST_BODY_TOO_LARGE"
    assert response.headers["x-request-id"]


def test_existing_routes_remain_registered() -> None:
    client = TestClient(app)
    responses = (
        client.get("/health"),
        client.post("/projects", json={"name": "phase 7.5 route check"}),
        client.post("/coze/projects", json={"project_name": "phase 7.5 route check"}),
        client.get("/system/r-env"),
        client.get("/system/docker-r-env"),
        client.get("/ui"),
        client.post("/task/create", json={}),
    )
    assert all(response.status_code != 404 for response in responses)
    assert all(response.headers.get("x-request-id") for response in responses)
