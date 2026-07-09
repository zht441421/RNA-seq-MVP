import json

import pytest

from backend.app.services.contrast_validation import (
    CONTRAST_VALIDATION_FAILED,
    ContrastValidationError,
    resolve_contrast,
)


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


def _metadata() -> list[dict]:
    return [
        {"sample_id": "sample_1", "condition": "control"},
        {"sample_id": "sample_2", "condition": "control"},
        {"sample_id": "sample_3", "condition": "treatment"},
        {"sample_id": "sample_4", "condition": "treatment"},
    ]


def _assert_safe_detail(detail: object) -> None:
    text = json.dumps(detail, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_PUBLIC_FRAGMENTS)


def _detail_for_invalid(**kwargs: object) -> dict:
    with pytest.raises(ContrastValidationError) as exc_info:
        resolve_contrast(_metadata(), **kwargs)
    detail = exc_info.value.to_detail()
    assert detail["error_code"] == CONTRAST_VALIDATION_FAILED
    _assert_safe_detail(detail)
    return detail


def test_valid_treatment_vs_control_contrast_is_accepted() -> None:
    contrast = resolve_contrast(
        _metadata(),
        contrast_column="condition",
        contrast_numerator="treatment",
        contrast_denominator="control",
    )

    assert contrast.as_dict() == {
        "contrast_column": "condition",
        "contrast_numerator": "treatment",
        "contrast_denominator": "control",
        "direction": "treatment_vs_control",
        "positive_log2fc_interpretation": "Higher in treatment relative to control",
        "negative_log2fc_interpretation": "Lower in treatment relative to control",
        "contrast_source": "explicit",
        "inferred": False,
    }


def test_numerator_missing_is_rejected() -> None:
    detail = _detail_for_invalid(
        contrast_column="condition",
        contrast_numerator="case",
        contrast_denominator="control",
    )

    assert any("contrast_numerator" in error for error in detail["errors"])


def test_denominator_missing_is_rejected() -> None:
    detail = _detail_for_invalid(
        contrast_column="condition",
        contrast_numerator="treatment",
        contrast_denominator="normal",
    )

    assert any("contrast_denominator" in error for error in detail["errors"])


def test_numerator_equals_denominator_is_rejected() -> None:
    detail = _detail_for_invalid(
        contrast_column="condition",
        contrast_numerator="control",
        contrast_denominator="control",
    )

    assert any("must be different" in error for error in detail["errors"])


def test_unsupported_contrast_column_is_rejected() -> None:
    detail = _detail_for_invalid(
        contrast_column="batch",
        contrast_numerator="treatment",
        contrast_denominator="control",
    )

    assert any("supports only 'condition'" in error for error in detail["errors"])


def test_one_sided_contrast_is_rejected() -> None:
    detail = _detail_for_invalid(
        contrast_numerator="treatment",
    )

    assert any("provided together" in error for error in detail["errors"])


def test_missing_condition_column_is_rejected() -> None:
    with pytest.raises(ContrastValidationError) as exc_info:
        resolve_contrast(
            [{"sample_id": "sample_1", "group": "control"}],
            contrast_column="condition",
            contrast_numerator="treatment",
            contrast_denominator="control",
        )

    detail = exc_info.value.to_detail()
    assert any("missing from metadata" in error for error in detail["errors"])
    _assert_safe_detail(detail)


def test_more_than_two_groups_is_rejected() -> None:
    metadata = [
        {"sample_id": "sample_1", "condition": "control"},
        {"sample_id": "sample_2", "condition": "treatment"},
        {"sample_id": "sample_3", "condition": "other"},
    ]

    with pytest.raises(ContrastValidationError) as exc_info:
        resolve_contrast(metadata)

    detail = exc_info.value.to_detail()
    assert any("exactly 2 groups" in error for error in detail["errors"])
    _assert_safe_detail(detail)


def test_empty_and_sensitive_values_are_reported_safely() -> None:
    detail = _detail_for_invalid(
        contrast_column="condition",
        contrast_numerator="token",
        contrast_denominator=r"D:\private\password.txt",
    )

    assert detail["errors"]
    _assert_safe_detail(detail)
