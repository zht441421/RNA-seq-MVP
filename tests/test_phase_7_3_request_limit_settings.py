import pytest

from backend.app.config import get_request_hardening_settings


VARIABLES = (
    "BIOINFO_MAX_REQUEST_BYTES",
    "BIOINFO_REQUEST_TIMEOUT_SECONDS",
    "BIOINFO_MAX_METADATA_BYTES",
    "BIOINFO_MAX_COUNT_MATRIX_BYTES",
)


@pytest.fixture(autouse=True)
def clear_settings(monkeypatch: pytest.MonkeyPatch):
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_request_hardening_is_disabled_by_default() -> None:
    settings = get_request_hardening_settings()
    assert settings.max_request_bytes == 0
    assert settings.request_timeout_seconds == 0
    assert settings.max_metadata_bytes == 0
    assert settings.max_count_matrix_bytes == 0


@pytest.mark.parametrize("value", [None, "", "  ", "0", "-1", "invalid"])
def test_unset_empty_zero_negative_and_invalid_byte_limits_disable_safely(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is not None:
        monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", value)
    assert get_request_hardening_settings().max_request_bytes == 0


def test_positive_byte_limits_are_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", "4096")
    monkeypatch.setenv("BIOINFO_MAX_METADATA_BYTES", "1024")
    monkeypatch.setenv("BIOINFO_MAX_COUNT_MATRIX_BYTES", "2048")
    settings = get_request_hardening_settings()
    assert settings.max_request_bytes == 4096
    assert settings.max_metadata_bytes == 1024
    assert settings.max_count_matrix_bytes == 2048


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", 0.0), ("0", 0.0), ("-2", 0.0), ("bad", 0.0), ("inf", 0.0), ("12", 12.0), ("1.5", 1.5)],
)
def test_timeout_setting_parsing(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: float
) -> None:
    monkeypatch.setenv("BIOINFO_REQUEST_TIMEOUT_SECONDS", value)
    assert get_request_hardening_settings().request_timeout_seconds == expected


def test_settings_representation_does_not_echo_raw_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsafe = "invalid-secret-config-value"
    monkeypatch.setenv("BIOINFO_MAX_REQUEST_BYTES", unsafe)
    settings = get_request_hardening_settings()
    assert unsafe not in str(settings)
    assert unsafe not in repr(settings)
