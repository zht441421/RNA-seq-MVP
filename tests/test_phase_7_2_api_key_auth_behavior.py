import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry


EXPECTED_KEY = "expected-local-test-key"
WRONG_KEY = "wrong-local-test-key"
DEFAULT_HEADER = "X-Bioinfo-API-Key"
UNSAFE_STATIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "traceback",
    "token=",
    "password=",
    "secret=",
    "bioinfo_api_key",
)


@pytest.fixture(autouse=True)
def isolated_auth_and_registry(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "BIOINFO_REQUIRE_API_KEY",
        "BIOINFO_API_KEY",
        "BIOINFO_API_KEY_HEADER",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_registry()
    yield
    reset_registry()


def _create_task(client: TestClient, headers: dict[str, str] | None = None):
    return client.post(
        "/task/create",
        headers=headers,
        json={
            "task_type": "bulk_rnaseq_placeholder",
            "parameters": {"project_name": "auth_test"},
        },
    )


def _assert_sanitized(response) -> None:
    body = json.dumps(response.json()).lower()
    for fragment in (*UNSAFE_STATIC_FRAGMENTS, EXPECTED_KEY, WRONG_KEY):
        assert fragment.lower() not in body


def test_disabled_mode_preserves_health_create_and_status() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200

    created = _create_task(client)
    assert created.status_code == 200

    status = client.get(f"/task/{created.json()['task_id']}/status")
    assert status.status_code == 200
    assert status.json()["task_id"] == created.json()["task_id"]


def test_enabled_mode_accepts_correct_key_for_post_and_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", EXPECTED_KEY)
    headers = {DEFAULT_HEADER: EXPECTED_KEY}
    client = TestClient(app)

    created = _create_task(client, headers)
    assert created.status_code == 200

    status = client.get(
        f"/task/{created.json()['task_id']}/status", headers=headers
    )
    assert status.status_code == 200


@pytest.mark.parametrize("provided", [None, WRONG_KEY])
def test_enabled_mode_rejects_missing_or_wrong_key_with_sanitized_401(
    monkeypatch: pytest.MonkeyPatch, provided: str | None
) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "yes")
    monkeypatch.setenv("BIOINFO_API_KEY", EXPECTED_KEY)
    headers = {} if provided is None else {DEFAULT_HEADER: provided}

    response = _create_task(TestClient(app), headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Valid API key required"}
    _assert_sanitized(response)


def test_enabled_mode_without_expected_key_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "on")
    monkeypatch.delenv("BIOINFO_API_KEY", raising=False)

    response = _create_task(TestClient(app))

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service authentication is unavailable"
    }
    _assert_sanitized(response)


def test_health_and_openapi_remain_public_when_auth_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", EXPECTED_KEY)
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_custom_header_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("BIOINFO_API_KEY", EXPECTED_KEY)
    monkeypatch.setenv("BIOINFO_API_KEY_HEADER", "X-Gateway-Key")

    response = _create_task(
        TestClient(app), {"X-Gateway-Key": EXPECTED_KEY}
    )

    assert response.status_code == 200


def test_invalid_auth_configuration_has_sanitized_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "invalid")

    response = _create_task(TestClient(app))

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service authentication is unavailable"
    }
    _assert_sanitized(response)
