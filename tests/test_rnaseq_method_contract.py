import json

import pytest

from backend.app.services.rnaseq_minimal import (
    FORMAL_DE_METHOD_NOT_IMPLEMENTED,
    MINIMAL_ANALYSIS_METHOD,
    RNASeqMethodContractError,
    UNSUPPORTED_ANALYSIS_METHOD,
    get_minimal_method_contract,
    get_supported_formal_methods,
    validate_requested_analysis_method,
    validate_requested_formal_de_method,
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


def _assert_no_forbidden_public_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_PUBLIC_FRAGMENTS)


def test_minimal_method_contract_fields_are_deterministic() -> None:
    first = get_minimal_method_contract()
    second = get_minimal_method_contract()

    assert first == second
    assert first["analysis_method"] == MINIMAL_ANALYSIS_METHOD
    assert (
        first["analysis_method_display_name"]
        == "Minimal CPM + preliminary log2 fold-change ranking"
    )
    assert first["formal_de_method"] is None
    assert first["formal_de_ready"] is False
    assert first["external_tools_called"] is False
    assert first["method_limitations"]


def test_supported_future_formal_methods_include_planned_methods() -> None:
    assert get_supported_formal_methods() == ["deseq2", "edger", "limma"]
    assert get_minimal_method_contract()["next_supported_formal_methods"] == [
        "deseq2",
        "edger",
        "limma",
    ]


def test_minimal_method_contract_records_no_formal_statistics() -> None:
    contract = get_minimal_method_contract()

    assert contract["statistical_test_performed"] is False
    assert contract["pvalue_available"] is False
    assert contract["adjusted_pvalue_available"] is False


@pytest.mark.parametrize("method", ["deseq2", "edger", "limma"])
@pytest.mark.parametrize(
    "validator",
    [validate_requested_analysis_method, validate_requested_formal_de_method],
)
def test_planned_formal_methods_are_rejected_as_not_implemented(
    method: str,
    validator,
) -> None:
    with pytest.raises(RNASeqMethodContractError) as exc_info:
        validator(method)

    exc = exc_info.value
    detail = exc.to_detail()
    assert exc.status_code == 501
    assert detail["error_code"] == FORMAL_DE_METHOD_NOT_IMPLEMENTED
    assert detail["requested_method"] == method
    assert method in detail["supported_future_formal_methods"]
    _assert_no_forbidden_public_fragments(detail)


def test_minimal_analysis_method_is_current_supported_method() -> None:
    assert validate_requested_analysis_method("minimal_cpm_log2fc") == MINIMAL_ANALYSIS_METHOD
    assert validate_requested_analysis_method(None) == MINIMAL_ANALYSIS_METHOD
    assert validate_requested_analysis_method("  ") == MINIMAL_ANALYSIS_METHOD


@pytest.mark.parametrize(
    ("method", "validator"),
    [
        ("wilcoxon", validate_requested_analysis_method),
        (r"C:\secret\custom_method", validate_requested_analysis_method),
        ("wilcoxon", validate_requested_formal_de_method),
    ],
)
def test_unsupported_arbitrary_method_is_rejected_safely(method: str, validator) -> None:
    with pytest.raises(RNASeqMethodContractError) as exc_info:
        validator(method)

    exc = exc_info.value
    detail = exc.to_detail()
    assert exc.status_code == 422
    assert detail["error_code"] == UNSUPPORTED_ANALYSIS_METHOD
    assert detail["requested_method"] == "unsupported"
    _assert_no_forbidden_public_fragments(detail)
