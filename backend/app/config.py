from functools import lru_cache
import math
import os
from pathlib import Path
import re

from pydantic import BaseModel, Field, SecretStr


API_KEY_HEADER_DEFAULT = "X-Bioinfo-API-Key"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"", "0", "false", "no", "off"})
_HTTP_HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
_DEFAULT_RATE_LIMIT_EXEMPT_PATHS = ("/health", "/docs", "/openapi.json")


def _parse_disabled_or_positive_int(value: str | None) -> int:
    """Parse a byte limit without echoing invalid configuration values."""
    normalized = "" if value is None else value.strip()
    if not normalized:
        return 0
    try:
        parsed = int(normalized)
    except ValueError:
        return 0
    return parsed if parsed > 0 else 0


def _parse_disabled_or_positive_number(value: str | None) -> float:
    normalized = "" if value is None else value.strip()
    if not normalized:
        return 0.0
    try:
        parsed = float(normalized)
    except ValueError:
        return 0.0
    return parsed if math.isfinite(parsed) and parsed > 0 else 0.0


class RequestHardeningSettings(BaseModel):
    max_request_bytes: int = 0
    request_timeout_seconds: float = 0.0
    max_metadata_bytes: int = 0
    max_count_matrix_bytes: int = 0


def get_request_hardening_settings() -> RequestHardeningSettings:
    return RequestHardeningSettings(
        max_request_bytes=_parse_disabled_or_positive_int(
            os.getenv("BIOINFO_MAX_REQUEST_BYTES")
        ),
        request_timeout_seconds=_parse_disabled_or_positive_number(
            os.getenv("BIOINFO_REQUEST_TIMEOUT_SECONDS")
        ),
        max_metadata_bytes=_parse_disabled_or_positive_int(
            os.getenv("BIOINFO_MAX_METADATA_BYTES")
        ),
        max_count_matrix_bytes=_parse_disabled_or_positive_int(
            os.getenv("BIOINFO_MAX_COUNT_MATRIX_BYTES")
        ),
    )


class RateLimitSettings(BaseModel):
    enabled: bool = False
    requests: int = 60
    window_seconds: int = 60
    scope: str = "ip"
    exempt_paths: tuple[str, ...] = _DEFAULT_RATE_LIMIT_EXEMPT_PATHS


def _parse_positive_int(value: str | None, default: int) -> int:
    normalized = "" if value is None else value.strip()
    if not normalized:
        return default
    try:
        parsed = int(normalized)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def get_rate_limit_settings() -> RateLimitSettings:
    enabled = _parse_required_api_key(os.getenv("RATE_LIMIT_ENABLED"))
    scope = os.getenv("RATE_LIMIT_SCOPE", "").strip().lower() or "ip"
    if scope != "ip":
        raise ValueError("invalid rate limiting configuration")

    configured_paths = os.getenv("RATE_LIMIT_EXEMPT_PATHS")
    exempt_paths = _DEFAULT_RATE_LIMIT_EXEMPT_PATHS
    if configured_paths is not None:
        exempt_paths = tuple(
            path.strip() for path in configured_paths.split(",") if path.strip()
        )

    return RateLimitSettings(
        enabled=enabled,
        requests=_parse_positive_int(os.getenv("RATE_LIMIT_REQUESTS"), 60),
        window_seconds=_parse_positive_int(
            os.getenv("RATE_LIMIT_WINDOW_SECONDS"), 60
        ),
        scope=scope,
        exempt_paths=exempt_paths,
    )


def _parse_required_api_key(value: str | None) -> bool:
    normalized = "" if value is None else value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError("invalid API key authentication configuration")


class APIKeyAuthSettings(BaseModel):
    require_api_key: bool
    api_key: SecretStr | None = Field(default=None, repr=False)
    api_key_header: str = API_KEY_HEADER_DEFAULT


def get_api_key_auth_settings() -> APIKeyAuthSettings:
    header_name = os.getenv("BIOINFO_API_KEY_HEADER", "").strip()
    if header_name and _HTTP_HEADER_NAME.fullmatch(header_name) is None:
        raise ValueError("invalid API key authentication configuration")
    return APIKeyAuthSettings(
        require_api_key=_parse_required_api_key(
            os.getenv("BIOINFO_REQUIRE_API_KEY")
        ),
        api_key=(
            SecretStr(os.environ["BIOINFO_API_KEY"])
            if "BIOINFO_API_KEY" in os.environ
            else None
        ),
        api_key_header=header_name or API_KEY_HEADER_DEFAULT,
    )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    app_name: str = "Bioinformatics Agent"
    app_version: str = "0.1.0"
    environment: str = "local"
    project_root: Path = Field(default_factory=_project_root)
    storage_dir: Path = Field(default_factory=lambda: _project_root() / ".storage")
    database_url: str = "sqlite:///./bioinformatics_agent.db"
    task_queue_backend: str = "mock"
    runner_backend: str = "mock"
    run_mode: str = Field(default_factory=lambda: os.getenv("RUN_MODE", "mock"))
    rscript_executable: str = Field(default_factory=lambda: os.getenv("RSCRIPT_EXECUTABLE", "Rscript"))
    docker_r_image: str = Field(
        default_factory=lambda: os.getenv("DOCKER_R_IMAGE", "bioinformatics-agent-r-bulk-rnaseq:0.1")
    )
    docker_executable: str = Field(default_factory=lambda: os.getenv("DOCKER_EXECUTABLE", "docker"))
    docker_workdir: str = Field(default_factory=lambda: os.getenv("DOCKER_WORKDIR", "/workspace"))
    max_preview_rows: int = 5
    low_count_min_total: int = 10


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
