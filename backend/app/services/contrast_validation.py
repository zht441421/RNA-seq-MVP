from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath


CONTRAST_VALIDATION_FAILED = "CONTRAST_VALIDATION_FAILED"
DEFAULT_CONTRAST_COLUMN = "condition"
SUPPORTED_CONTRAST_COLUMNS = (DEFAULT_CONTRAST_COLUMN,)

_MAX_CONTRAST_VALUE_LENGTH = 128
_SENSITIVE_RE = re.compile(r"traceback|token|password|secret", re.IGNORECASE)
_DIRECTION_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_PATH_REPLACEMENTS = (
    re.compile(r"file://[^\s,;)\]}\"']*", re.IGNORECASE),
    re.compile(r"[A-Za-z]:[\\/][^\s,;)\]}\"']*"),
    re.compile(r"/home/[^\s,;)\]}\"']*", re.IGNORECASE),
    re.compile(r"/mnt/[^\s,;)\]}\"']*", re.IGNORECASE),
)


@dataclass(frozen=True)
class ContrastSpec:
    contrast_column: str
    contrast_numerator: str
    contrast_denominator: str
    contrast_source: str

    @property
    def direction(self) -> str:
        numerator = _direction_token(self.contrast_numerator)
        denominator = _direction_token(self.contrast_denominator)
        return f"{numerator}_vs_{denominator}"

    @property
    def positive_log2fc_interpretation(self) -> str:
        return (
            f"Higher in {self.contrast_numerator} relative to "
            f"{self.contrast_denominator}"
        )

    @property
    def negative_log2fc_interpretation(self) -> str:
        return (
            f"Lower in {self.contrast_numerator} relative to "
            f"{self.contrast_denominator}"
        )

    @property
    def inferred(self) -> bool:
        return self.contrast_source == "inferred"

    def as_dict(self) -> dict:
        return {
            "contrast_column": _sanitize_public_text(self.contrast_column),
            "contrast_numerator": _sanitize_public_text(self.contrast_numerator),
            "contrast_denominator": _sanitize_public_text(self.contrast_denominator),
            "direction": _sanitize_public_text(self.direction),
            "positive_log2fc_interpretation": _sanitize_public_text(
                self.positive_log2fc_interpretation
            ),
            "negative_log2fc_interpretation": _sanitize_public_text(
                self.negative_log2fc_interpretation
            ),
            "contrast_source": self.contrast_source,
            "inferred": self.inferred,
        }


class ContrastValidationError(ValueError):
    def __init__(
        self,
        errors: list[str],
        *,
        message: str = "Contrast validation failed.",
        status_code: int = 422,
    ) -> None:
        self.error_code = CONTRAST_VALIDATION_FAILED
        self.message = message
        self.status_code = status_code
        self.errors = _unique_non_empty(
            [_sanitize_public_text(error) for error in errors]
        ) or [message]
        super().__init__(message)

    def to_detail(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "errors": list(self.errors),
        }


def resolve_contrast(
    metadata: list[dict],
    *,
    contrast_column: str | None = None,
    contrast_numerator: str | None = None,
    contrast_denominator: str | None = None,
    supported_columns: tuple[str, ...] = SUPPORTED_CONTRAST_COLUMNS,
) -> ContrastSpec:
    raw_inputs = {
        "contrast_column": contrast_column,
        "contrast_numerator": contrast_numerator,
        "contrast_denominator": contrast_denominator,
    }
    cleaned_inputs = {
        field: _clean_cell(value)
        for field, value in raw_inputs.items()
    }
    provided = {
        field: value is not None
        for field, value in raw_inputs.items()
    }
    errors: list[str] = []

    for field, raw_value in raw_inputs.items():
        if raw_value is not None and not cleaned_inputs[field]:
            errors.append(f"{field} must be a non-empty value when provided.")
        if raw_value is not None and _is_malformed_contrast_value(cleaned_inputs[field]):
            errors.append(f"{field} contains a malformed or unsafe value.")

    requested_column = cleaned_inputs["contrast_column"] or DEFAULT_CONTRAST_COLUMN
    if requested_column not in supported_columns:
        errors.append(
            (
                "Unsupported contrast_column. Current MVP supports only "
                f"{DEFAULT_CONTRAST_COLUMN!r}."
            )
        )

    normalized_metadata = _normalize_metadata_rows(metadata)
    metadata_columns = set().union(*(row.keys() for row in normalized_metadata)) if normalized_metadata else set()
    if requested_column not in metadata_columns:
        errors.append(
            f"contrast_column {requested_column!r} is missing from metadata."
        )

    condition_values = _metadata_values(normalized_metadata, requested_column)
    if requested_column in metadata_columns and len(condition_values) != 2:
        errors.append(
            (
                "Current MVP supports exactly 2 groups in "
                f"contrast_column {requested_column!r}; found {len(condition_values)}."
            )
        )

    explicit_request = any(provided.values())
    if explicit_request:
        numerator_provided = provided["contrast_numerator"]
        denominator_provided = provided["contrast_denominator"]
        if numerator_provided != denominator_provided:
            errors.append(
                "contrast_numerator and contrast_denominator must be provided together."
            )
        if provided["contrast_column"] and not numerator_provided and not denominator_provided:
            errors.append(
                (
                    "contrast_numerator and contrast_denominator are required when "
                    "contrast_column is provided."
                )
            )

        numerator = cleaned_inputs["contrast_numerator"]
        denominator = cleaned_inputs["contrast_denominator"]
        if numerator and denominator:
            if numerator == denominator:
                errors.append("contrast_numerator and contrast_denominator must be different.")
            if condition_values and numerator not in condition_values:
                errors.append(
                    f"contrast_numerator {numerator!r} is not present in metadata."
                )
            if condition_values and denominator not in condition_values:
                errors.append(
                    f"contrast_denominator {denominator!r} is not present in metadata."
                )
    else:
        numerator = condition_values[1] if len(condition_values) == 2 else ""
        denominator = condition_values[0] if len(condition_values) == 2 else ""

    if errors:
        raise ContrastValidationError(errors)

    return ContrastSpec(
        contrast_column=requested_column,
        contrast_numerator=numerator,
        contrast_denominator=denominator,
        contrast_source="explicit" if explicit_request else "inferred",
    )


def contrast_payload_from_mapping(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    required = {
        "contrast_column",
        "contrast_numerator",
        "contrast_denominator",
        "direction",
        "positive_log2fc_interpretation",
        "negative_log2fc_interpretation",
    }
    if not required.intersection(value.keys()):
        return None
    payload = {
        "contrast_column": _sanitize_public_text(value.get("contrast_column", "")),
        "contrast_numerator": _sanitize_public_text(
            value.get("contrast_numerator", "")
        ),
        "contrast_denominator": _sanitize_public_text(
            value.get("contrast_denominator", "")
        ),
        "direction": _sanitize_public_text(value.get("direction", "")),
        "positive_log2fc_interpretation": _sanitize_public_text(
            value.get("positive_log2fc_interpretation", "")
        ),
        "negative_log2fc_interpretation": _sanitize_public_text(
            value.get("negative_log2fc_interpretation", "")
        ),
    }
    if "contrast_source" in value:
        payload["contrast_source"] = _sanitize_public_text(value.get("contrast_source", ""))
    if "inferred" in value:
        payload["inferred"] = bool(value.get("inferred"))
    return payload


def _normalize_metadata_rows(metadata: list[dict]) -> list[dict]:
    return [
        {
            _clean_cell(key): _clean_cell(value)
            for key, value in row.items()
            if key is not None
        }
        for row in metadata
    ]


def _metadata_values(metadata: list[dict], column: str) -> list[str]:
    values: list[str] = []
    for row in metadata:
        value = _clean_cell(row.get(column))
        if value and value not in values:
            values.append(value)
    return values


def _is_malformed_contrast_value(value: str) -> bool:
    if not value:
        return False
    if len(value) > _MAX_CONTRAST_VALUE_LENGTH:
        return True
    if "\x00" in value or any(ord(character) < 32 for character in value):
        return True
    if value.lower().startswith("file://"):
        return True
    if "/" in value or "\\" in value:
        return True
    posix_path = PurePosixPath(value.replace("\\", "/"))
    windows_path = PureWindowsPath(value)
    return bool(
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    )


def _direction_token(value: str) -> str:
    token = _DIRECTION_TOKEN_RE.sub("_", _sanitize_public_text(value)).strip("_")
    return token or "unknown"


def _sanitize_public_text(value: object) -> str:
    text = str(value or "").strip()
    for pattern in _PATH_REPLACEMENTS:
        text = pattern.sub("[redacted-path]", text)
    text = _SENSITIVE_RE.sub("redacted", text)
    if _looks_like_absolute_path(text):
        return PurePosixPath(text.replace("\\", "/")).name or "redacted"
    return text


def _looks_like_absolute_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(normalized)
    return bool(
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or normalized.lower().startswith("/home/")
        or normalized.lower().startswith("/mnt/")
    )


def _clean_cell(value: object) -> str:
    return "" if value is None else str(value).strip()


def _unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            unique_values.append(text)
            seen.add(text)
    return unique_values
