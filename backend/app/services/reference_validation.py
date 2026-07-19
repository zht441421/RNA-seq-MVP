"""Offline reference-dataset and Golden Result validation helpers.

This module compares stable behavioral contracts only. It is deliberately
isolated from RNA-seq and DESeq2 execution code.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


ALLOWED_DATASET_CLASSIFICATIONS = {
    "workflow_fixture",
    "reference_dataset",
    "scientific_benchmark_dataset",
}
ALLOWED_DATA_NATURES = {"synthetic", "miniature", "real_public"}
REQUIRED_DATASET_FIELDS = {
    "dataset_id",
    "dataset_type",
    "classification",
    "data_nature",
    "source",
    "usage_terms",
    "expected_files",
    "metadata_schema",
    "count_matrix_schema",
    "contrast",
    "expected_sample_count",
    "expected_gene_count",
    "intended_validation_purpose",
    "known_limitations",
    "scientific_validation_suitable",
    "golden_result",
}
REQUIRED_GOLDEN_FIELDS = {
    "golden_result_version",
    "dataset_id",
    "description",
    "comparison_modes",
    "checks",
    "scientific_boundaries",
}
PUBLIC_DATASET_REQUIRED_FIELDS = {
    "validation_scope",
    "biological_interpretation_scope",
    "provenance",
    "license",
    "citation",
    "accession",
    "source_version",
    "retrieval_date",
    "retrieval",
    "preprocessing",
    "expected_environment_requirements",
}
REQUIRED_CHECK_GROUPS = {
    "exact",
    "required_fields",
    "accepted_values",
    "numeric_ranges",
    "required_artifact_categories",
    "forbidden_fields",
    "forbidden_claims",
    "environment_dependent",
}


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON document must contain an object.")
    return value


def validate_reference_manifest(
    manifest: dict[str, Any],
    *,
    repository_root: Path | None = None,
    verify_local_files: bool = False,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("manifest_version") not in {"1.0", "1.1"}:
        errors.append("manifest_version must be 1.0 or 1.1")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        return [*errors, "datasets must be a non-empty array"]

    identifiers: set[str] = set()
    for index, dataset in enumerate(datasets):
        label = f"datasets[{index}]"
        if not isinstance(dataset, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = sorted(REQUIRED_DATASET_FIELDS - set(dataset))
        if missing:
            errors.append(f"{label} missing fields: {', '.join(missing)}")
        dataset_id = dataset.get("dataset_id")
        if not isinstance(dataset_id, str) or not dataset_id.strip():
            errors.append(f"{label}.dataset_id must be a non-empty string")
        elif dataset_id in identifiers:
            errors.append(f"duplicate dataset_id: {dataset_id}")
        else:
            identifiers.add(dataset_id)
        if dataset.get("classification") not in ALLOWED_DATASET_CLASSIFICATIONS:
            errors.append(f"{label}.classification is invalid")
        if dataset.get("data_nature") not in ALLOWED_DATA_NATURES:
            errors.append(f"{label}.data_nature is invalid")
        if not isinstance(dataset.get("scientific_validation_suitable"), bool):
            errors.append(f"{label}.scientific_validation_suitable must be boolean")
        if dataset.get("data_nature") == "synthetic" and dataset.get(
            "scientific_validation_suitable"
        ) is not False:
            errors.append(f"{label} synthetic data cannot be scientific validation data")
        if dataset.get("data_nature") == "real_public":
            public_missing = sorted(PUBLIC_DATASET_REQUIRED_FIELDS - set(dataset))
            if public_missing:
                errors.append(
                    f"{label} missing real-public fields: {', '.join(public_missing)}"
                )
            if dataset.get("classification") != "reference_dataset":
                errors.append(f"{label} real public validation data must be a reference_dataset")
            source = dataset.get("source")
            if not isinstance(source, dict) or not str(source.get("url") or "").startswith("https://"):
                errors.append(f"{label}.source.url must be a public HTTPS URL")
            for field in ("license", "citation", "accession", "source_version"):
                if not isinstance(dataset.get(field), str) or not dataset[field].strip():
                    errors.append(f"{label}.{field} must be a non-empty string")
        limitations = dataset.get("known_limitations")
        if not isinstance(limitations, list) or not limitations:
            errors.append(f"{label}.known_limitations must be a non-empty array")
        expected_files = dataset.get("expected_files")
        if not isinstance(expected_files, list) or not expected_files:
            errors.append(f"{label}.expected_files must be a non-empty array")
            continue
        for file_index, file_entry in enumerate(expected_files):
            file_label = f"{label}.expected_files[{file_index}]"
            errors.extend(
                _validate_file_entry(
                    file_entry,
                    file_label,
                    repository_root=repository_root,
                    verify_local_files=verify_local_files,
                )
            )
    return errors


def validate_golden_result(golden: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_GOLDEN_FIELDS - set(golden))
    if missing:
        errors.append("Golden Result missing fields: " + ", ".join(missing))
    if golden.get("golden_result_version") not in {"1.0", "1.1"}:
        errors.append("golden_result_version must be 1.0 or 1.1")
    checks = golden.get("checks")
    if not isinstance(checks, dict):
        return [*errors, "checks must be an object"]
    missing_checks = sorted(REQUIRED_CHECK_GROUPS - set(checks))
    if missing_checks:
        errors.append("checks missing groups: " + ", ".join(missing_checks))
    for name in ("exact", "accepted_values", "numeric_ranges", "environment_dependent"):
        if name in checks and not isinstance(checks[name], dict):
            errors.append(f"checks.{name} must be an object")
    for name in (
        "required_fields",
        "required_artifact_categories",
        "forbidden_fields",
        "forbidden_claims",
    ):
        if name in checks and not isinstance(checks[name], list):
            errors.append(f"checks.{name} must be an array")
    boundaries = golden.get("scientific_boundaries")
    if not isinstance(boundaries, dict):
        errors.append("scientific_boundaries must be an object")
    elif boundaries.get("golden_result_validates") != "system_behavior_not_biological_truth":
        errors.append("Golden Result must validate system behavior, not biological truth")
    optional_groups = {
        "numeric_tolerances": dict,
        "sign_comparisons": dict,
        "overlap_thresholds": dict,
        "unordered_sets": dict,
        "finite_fields": list,
        "forbidden_text_patterns": list,
        "required_text_concepts": dict,
    }
    for name, expected_type in optional_groups.items():
        if name in checks and not isinstance(checks[name], expected_type):
            errors.append(f"checks.{name} must be a {expected_type.__name__}")
    return errors


def compare_golden_result(
    observed: dict[str, Any],
    golden: dict[str, Any],
    *,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    schema_errors = validate_golden_result(golden)
    if schema_errors:
        return {"passed": False, "checks": [], "failures": schema_errors}

    checks_run: list[dict[str, Any]] = []
    failures: list[str] = []
    checks = golden["checks"]

    for field, expected in checks["exact"].items():
        actual, present = _lookup(observed, field)
        _record(checks_run, failures, "exact", field, present and actual == expected)

    for field in checks["required_fields"]:
        _, present = _lookup(observed, field)
        _record(checks_run, failures, "required_field", field, present)

    for field, accepted in checks["accepted_values"].items():
        actual, present = _lookup(observed, field)
        _record(
            checks_run,
            failures,
            "accepted_values",
            field,
            present and actual in accepted,
        )

    for field, bounds in checks["numeric_ranges"].items():
        actual, present = _lookup(observed, field)
        valid = present and isinstance(actual, (int, float)) and not isinstance(actual, bool)
        if valid and bounds.get("min") is not None:
            valid = actual >= bounds["min"]
        if valid and bounds.get("max") is not None:
            valid = actual <= bounds["max"]
        _record(checks_run, failures, "numeric_range", field, bool(valid))

    for field, rule in checks.get("numeric_tolerances", {}).items():
        actual, present = _lookup(observed, field)
        expected = rule.get("expected") if isinstance(rule, dict) else None
        valid = _finite_number(actual) and _finite_number(expected)
        if valid:
            absolute = abs(float(actual) - float(expected))
            absolute_limit = float(rule.get("absolute", 0.0))
            relative_limit = float(rule.get("relative", 0.0))
            relative = absolute / max(abs(float(expected)), 1e-300)
            valid = absolute <= absolute_limit or relative <= relative_limit
        _record(checks_run, failures, "numeric_tolerance", field, present and bool(valid))

    for field, expected_sign in checks.get("sign_comparisons", {}).items():
        actual, present = _lookup(observed, field)
        sign = "zero"
        if _finite_number(actual):
            sign = "positive" if actual > 0 else "negative" if actual < 0 else "zero"
        _record(checks_run, failures, "sign", field, present and sign == expected_sign)

    for field, rule in checks.get("overlap_thresholds", {}).items():
        actual, present = _lookup(observed, field)
        expected = set(rule.get("expected", [])) if isinstance(rule, dict) else set()
        actual_values = list(actual) if isinstance(actual, list) else []
        top_n = int(rule.get("top_n", len(actual_values)))
        overlap = len(set(actual_values[:top_n]) & expected)
        minimum = int(rule.get("minimum_overlap", len(expected)))
        _record(checks_run, failures, "overlap", field, present and overlap >= minimum)

    for field, rule in checks.get("unordered_sets", {}).items():
        actual, present = _lookup(observed, field)
        expected = set(rule.get("expected", [])) if isinstance(rule, dict) else set()
        actual_set = set(actual) if isinstance(actual, list) else set()
        mode = rule.get("mode", "exact") if isinstance(rule, dict) else "exact"
        valid = expected.issubset(actual_set) if mode == "subset" else expected == actual_set
        _record(checks_run, failures, "unordered_set", field, present and valid)

    for field in checks.get("finite_fields", []):
        actual, present = _lookup(observed, field)
        values = actual if isinstance(actual, list) else [actual]
        valid = present and bool(values) and all(_finite_number(value) for value in values)
        _record(checks_run, failures, "finite", field, valid)

    # Non-finite observations must produce failed checks, not crash the verifier.
    # JSON's NaN/Infinity spellings are safe here because this rendering is used
    # only for defensive text-pattern matching and is never emitted as a report.
    rendered_observation = json.dumps(
        observed, sort_keys=True, allow_nan=True, default=str
    ).lower()
    for pattern in checks.get("forbidden_text_patterns", []):
        try:
            absent = re.search(str(pattern), rendered_observation, re.IGNORECASE) is None
        except re.error:
            absent = False
        _record(checks_run, failures, "forbidden_text", str(pattern), absent)

    for field, concepts in checks.get("required_text_concepts", {}).items():
        actual, present = _lookup(observed, field)
        rendered = " ".join(str(value) for value in actual) if isinstance(actual, list) else str(actual or "")
        for concept in concepts:
            _record(
                checks_run,
                failures,
                "required_text_concept",
                f"{field}:{concept}",
                present and str(concept).lower() in rendered.lower(),
            )

    artifact_categories = set(observed.get("artifact_categories") or [])
    for category in checks["required_artifact_categories"]:
        _record(
            checks_run,
            failures,
            "artifact_category",
            category,
            category in artifact_categories,
        )

    for field in checks["forbidden_fields"]:
        _, present = _lookup(observed, field)
        _record(checks_run, failures, "forbidden_field", field, not present)

    claims = [str(value).lower() for value in observed.get("claims") or []]
    for claim in checks["forbidden_claims"]:
        absent = all(str(claim).lower() not in value for value in claims)
        _record(checks_run, failures, "forbidden_claim", claim, absent)

    environment_values = environment or {}
    for field, rule in checks["environment_dependent"].items():
        environment_key = rule.get("environment_key")
        branch = "when_true" if environment_values.get(environment_key) is True else "when_false"
        expectation = rule.get(branch, {})
        actual, present = _lookup(observed, field)
        accepted = expectation.get("accepted_values", [])
        _record(
            checks_run,
            failures,
            "environment_dependent",
            field,
            present and actual in accepted,
        )

    return {"passed": not failures, "checks": checks_run, "failures": failures}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_tool_openapi_compatibility(
    tool_manifest: dict[str, Any], openapi: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    tools = tool_manifest.get("tools")
    if not isinstance(tools, list) or len(tools) != 7:
        return ["Coze tool manifest must contain exactly seven tools"]
    expected_names = {
        "create_analysis_task",
        "validate_input",
        "start_analysis",
        "get_task_status",
        "get_analysis_summary",
        "list_artifacts",
        "download_artifact",
    }
    names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
    if names != expected_names:
        errors.append("Coze tool names do not match the Phase 8.2 contract")
    for tool in tools:
        if not isinstance(tool, dict):
            errors.append("Coze tool entry must be an object")
            continue
        binding = tool.get("http") or {}
        method = str(binding.get("method") or "").lower()
        path = str(binding.get("path") or "")
        operation = openapi.get("paths", {}).get(path, {}).get(method, {})
        if operation.get("operationId") != binding.get("operation_id"):
            errors.append(f"OpenAPI binding mismatch for tool: {tool.get('name')}")
    duplicates = duplicate_openapi_operation_ids(openapi)
    if duplicates:
        errors.append("Duplicate OpenAPI operation IDs: " + ", ".join(duplicates))
    return errors


def duplicate_openapi_operation_ids(openapi: dict[str, Any]) -> list[str]:
    counts: dict[str, int] = {}
    for path_item in openapi.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if isinstance(operation_id, str) and operation_id:
                counts[operation_id] = counts.get(operation_id, 0) + 1
    return sorted(operation_id for operation_id, count in counts.items() if count > 1)


def _validate_file_entry(
    value: Any,
    label: str,
    *,
    repository_root: Path | None,
    verify_local_files: bool,
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    errors: list[str] = []
    for field in ("role", "path", "sha256"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            errors.append(f"{label}.{field} must be a non-empty string")
    path_value = str(value.get("path") or "")
    if _is_unsafe_path(path_value):
        errors.append(f"{label}.path must be repository-relative and traversal-free")
    checksum = str(value.get("sha256") or "")
    if checksum and (len(checksum) != 64 or any(character not in "0123456789abcdefABCDEF" for character in checksum)):
        errors.append(f"{label}.sha256 must be a SHA-256 hex digest")
    storage = str(value.get("storage") or "repository")
    if storage not in {"repository", "cache", "prepared_cache"}:
        errors.append(f"{label}.storage is invalid")
    if verify_local_files and storage == "repository" and repository_root is not None and not errors:
        local_path = repository_root / Path(*PurePosixPath(path_value).parts)
        if not local_path.is_file():
            errors.append(f"{label} referenced local file is missing")
        elif sha256_file(local_path).lower() != checksum.lower():
            errors.append(f"{label} checksum mismatch")
    return errors


def _is_unsafe_path(value: str) -> bool:
    posix = PurePosixPath(value.replace("\\", "/"))
    windows = PureWindowsPath(value)
    return bool(
        not value
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    )


def _lookup(value: dict[str, Any], dotted_path: str) -> tuple[Any, bool]:
    current: Any = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]
    return current, True


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _record(
    checks: list[dict[str, Any]],
    failures: list[str],
    mode: str,
    field: str,
    passed: bool,
) -> None:
    checks.append({"mode": mode, "field": field, "passed": bool(passed)})
    if not passed:
        failures.append(f"{mode} check failed: {field}")
