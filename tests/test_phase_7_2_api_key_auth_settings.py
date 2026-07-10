import pytest

from backend.app.config import (
    API_KEY_HEADER_DEFAULT,
    get_api_key_auth_settings,
)


def test_auth_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOINFO_REQUIRE_API_KEY", raising=False)
    monkeypatch.delenv("BIOINFO_API_KEY", raising=False)
    monkeypatch.delenv("BIOINFO_API_KEY_HEADER", raising=False)

    settings = get_api_key_auth_settings()

    assert settings.require_api_key is False
    assert settings.api_key is None


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " on "])
def test_accepted_true_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", value)
    assert get_api_key_auth_settings().require_api_key is True


@pytest.mark.parametrize(
    "value", [None, "", "0", "false", "FALSE", "no", "off", " off "]
)
def test_accepted_false_values(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("BIOINFO_REQUIRE_API_KEY", raising=False)
    else:
        monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", value)
    assert get_api_key_auth_settings().require_api_key is False


def test_default_and_custom_header_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOINFO_API_KEY_HEADER", raising=False)
    assert get_api_key_auth_settings().api_key_header == API_KEY_HEADER_DEFAULT

    monkeypatch.setenv("BIOINFO_API_KEY_HEADER", "X-Gateway-Key")
    assert get_api_key_auth_settings().api_key_header == "X-Gateway-Key"


def test_settings_string_does_not_expose_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_value = "settings-secret-value"
    monkeypatch.setenv("BIOINFO_API_KEY", secret_value)

    settings = get_api_key_auth_settings()

    assert secret_value not in str(settings)
    assert secret_value not in repr(settings)


def test_invalid_boolean_or_header_configuration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "sometimes")
    with pytest.raises(ValueError, match="invalid API key authentication"):
        get_api_key_auth_settings()

    monkeypatch.setenv("BIOINFO_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("BIOINFO_API_KEY_HEADER", "invalid header")
    with pytest.raises(ValueError, match="invalid API key authentication"):
        get_api_key_auth_settings()
