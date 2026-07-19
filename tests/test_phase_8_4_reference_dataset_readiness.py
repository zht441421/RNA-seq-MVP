import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.contracts.coze_tools import build_coze_tool_manifest
from backend.app.main import app
from backend.app.services.local_agent_simulator import LocalAgentSimulator
from backend.app.services.reference_validation import (
    compare_golden_result,
    duplicate_openapi_operation_ids,
    load_json_object,
    validate_golden_result,
    validate_reference_manifest,
    validate_tool_openapi_compatibility,
)
from backend.app.services.task_registry import reset_registry


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/reference-datasets/reference-dataset-manifest.json"
GOLDEN_PATH = ROOT / "docs/reference-datasets/golden-results/phase-8-4-rnaseq-minimal-synthetic-v1.json"
DEMO_METADATA = "rnaseq_minimal/metadata.csv"
DEMO_COUNTS = "rnaseq_minimal/counts.csv"
FORBIDDEN_PUBLIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "traceback",
    "password=",
    "token=",
    "secret=",
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    for name in (
        "BIOINFO_REQUIRE_API_KEY",
        "BIOINFO_API_KEY",
        "RATE_LIMIT_ENABLED",
        "BIOINFO_MAX_REQUEST_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str((ROOT / "data/demo").resolve()))
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "state/tasks.sqlite3"))
    reset_registry()
    yield output_root
    reset_registry()


def _manifest() -> dict:
    return load_json_object(MANIFEST_PATH)


def _golden() -> dict:
    return load_json_object(GOLDEN_PATH)


def _valid_observation() -> dict:
    golden = _golden()
    return {
        **golden["checks"]["exact"],
        "input_gene_count": 10,
        "reliability_information": {
            "available": False,
            "grade": None,
            "strong_conclusion_allowed": False,
        },
        "warnings": ["No formal statistical test was performed."],
        "limitations": ["Exploratory workflow only."],
        "interpretation_boundary": "Exploratory CPM/log2FC ranking is not formal differential expression statistics.",
        "summary_fields": golden["expected_summary_schema_fields"],
        "artifact_categories": golden["checks"]["required_artifact_categories"],
        "claims": [],
        "deseq2_execution_state": "not_requested",
    }


def _workflow_request() -> dict:
    return {
        "project_name": "phase_8_4_reference_validation",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "analysis_goal": ["qc", "differential_expression"],
        "metadata_file": DEMO_METADATA,
        "count_matrix_file": DEMO_COUNTS,
        "sample_id_column": "sample_id",
        "group_column": "condition",
        "contrast_numerator": "treatment",
        "contrast_denominator": "control",
        "execution_mode": "minimal_real",
        "analysis_method": "minimal_cpm_log2fc",
    }


def test_reference_dataset_manifest_schema_and_checksums_are_valid() -> None:
    manifest = _manifest()
    assert validate_reference_manifest(
        manifest, repository_root=ROOT, verify_local_files=True
    ) == []
    dataset = manifest["datasets"][0]
    assert dataset["classification"] == "workflow_fixture"
    assert dataset["data_nature"] == "synthetic"
    assert dataset["scientific_validation_suitable"] is False
    assert dataset["expected_sample_count"] == {"exact": 6}
    assert dataset["expected_gene_count"] == {"min": 10, "max": 10}
    assert dataset["known_limitations"]


def test_manifest_rejects_invalid_dataset_classification() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["datasets"][0]["classification"] = "production_truth"
    errors = validate_reference_manifest(manifest)
    assert any("classification is invalid" in error for error in errors)


def test_manifest_detects_checksum_mismatch() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["datasets"][0]["expected_files"][0]["sha256"] = "0" * 64
    errors = validate_reference_manifest(
        manifest, repository_root=ROOT, verify_local_files=True
    )
    assert any("checksum mismatch" in error for error in errors)


def test_golden_result_schema_and_scientific_boundary_are_valid() -> None:
    golden = _golden()
    assert validate_golden_result(golden) == []
    boundaries = golden["scientific_boundaries"]
    assert boundaries["workflow_classification"] == "exploratory"
    assert boundaries["pvalues_expected"] is False
    assert boundaries["adjusted_pvalues_expected"] is False
    assert boundaries["statistical_significance_claims_allowed"] is False
    assert boundaries["synthetic_fixture_is_scientific_evidence"] is False
    assert golden["deseq2_requirement"]["mode"] == "environment_dependent"


def test_golden_result_rejects_missing_required_fields() -> None:
    golden = copy.deepcopy(_golden())
    golden.pop("scientific_boundaries")
    errors = validate_golden_result(golden)
    assert any("scientific_boundaries" in error for error in errors)


def test_golden_comparison_supports_exact_presence_sets_ranges_and_forbidden_values() -> None:
    comparison = compare_golden_result(
        _valid_observation(), _golden(), environment={"deseq2_ready": False}
    )
    assert comparison["passed"] is True
    assert {check["mode"] for check in comparison["checks"]} >= {
        "exact",
        "required_field",
        "accepted_values",
        "numeric_range",
        "artifact_category",
        "forbidden_field",
        "forbidden_claim",
        "environment_dependent",
    }


def test_golden_comparison_reports_missing_fields_checksum_independent_claims_and_ranges() -> None:
    observed = _valid_observation()
    observed.pop("interpretation_boundary")
    observed["input_gene_count"] = 11
    observed["artifact_categories"].remove("minimal_analysis_report")
    observed["reported_pvalues"] = [0.01]
    observed["claims"] = ["GeneAlpha is statistically significant."]
    comparison = compare_golden_result(
        observed, _golden(), environment={"deseq2_ready": False}
    )
    assert comparison["passed"] is False
    assert any("interpretation_boundary" in failure for failure in comparison["failures"])
    assert any("input_gene_count" in failure for failure in comparison["failures"])
    assert any("minimal_analysis_report" in failure for failure in comparison["failures"])
    assert any("reported_pvalues" in failure for failure in comparison["failures"])
    assert any("statistically significant" in failure for failure in comparison["failures"])


@pytest.mark.parametrize(
    ("ready", "state", "expected_pass"),
    [
        (False, "unavailable", True),
        (False, "completed", False),
        (True, "available_for_separate_validation", True),
        (True, "completed", False),
    ],
)
def test_deseq2_expectation_remains_environment_dependent(
    ready: bool, state: str, expected_pass: bool
) -> None:
    observed = _valid_observation()
    observed["deseq2_execution_state"] = state
    comparison = compare_golden_result(
        observed, _golden(), environment={"deseq2_ready": ready}
    )
    assert comparison["passed"] is expected_pass


def test_openapi_and_coze_manifest_bindings_are_compatible_and_unique() -> None:
    manifest = build_coze_tool_manifest()
    openapi = app.openapi()
    assert validate_tool_openapi_compatibility(manifest, openapi) == []
    assert duplicate_openapi_operation_ids(openapi) == []

    duplicate = copy.deepcopy(openapi)
    duplicate["paths"]["/phase-8-4-duplicate"] = {
        "get": {
            "operationId": manifest["tools"][0]["http"]["operation_id"],
            "responses": {"200": {"description": "test"}},
        }
    }
    assert duplicate_openapi_operation_ids(duplicate) == [
        manifest["tools"][0]["http"]["operation_id"]
    ]
    assert any(
        "Duplicate OpenAPI operation IDs" in error
        for error in validate_tool_openapi_compatibility(manifest, duplicate)
    )


def test_phase_8_4_materials_contain_no_real_secret_or_local_absolute_path() -> None:
    paths = [
        ROOT / "docs/reference-datasets/README.md",
        MANIFEST_PATH,
        GOLDEN_PATH,
        ROOT / "docs/phase-8-4-reference-dataset-deployment-readiness.md",
        ROOT / "docs/examples/deployment/phase-8-4.env.example",
        ROOT / "docs/deployment/phase-8-4-coze-plugin-package.json",
    ]
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert fragment not in rendered
    env_text = paths[4].read_text(encoding="utf-8")
    assert "BIOINFO_API_KEY=<set-in-deployment-secret-store>" in env_text
    package = json.loads(paths[5].read_text(encoding="utf-8"))
    assert package["base_url"]["value"] is None
    assert package["authentication"]["credential_in_package"] is False
    assert package["publication"] == {
        "performed": False,
        "staging_deployment_performed": False,
        "production_endpoint_created": False,
    }


def test_existing_coze_tool_contract_remains_backward_compatible() -> None:
    stored = load_json_object(ROOT / "docs/coze-tool-manifest.json")
    assert stored == build_coze_tool_manifest()
    assert [tool["name"] for tool in stored["tools"]] == [
        "create_analysis_task",
        "validate_input",
        "start_analysis",
        "get_task_status",
        "get_analysis_summary",
        "list_artifacts",
        "download_artifact",
    ]


def test_phase_8_4_offline_readiness_gate_passes_without_network() -> None:
    from scripts.verify_phase_8_4_reference_dataset_readiness import (
        verify_readiness,
    )

    assert verify_readiness() == []


def test_reference_fixture_end_to_end_matches_golden_result(
    isolated_environment: Path,
) -> None:
    workflow = LocalAgentSimulator(TestClient(app)).simulate_workflow(
        _workflow_request()
    )
    assert workflow["completed"] is True
    task_id = workflow["task_id"]
    qc_summary = load_json_object(
        isolated_environment / "tasks" / task_id / "qc_summary.json"
    )
    summary = workflow["summary"]
    artifacts = workflow["artifacts"]["artifacts"]
    observed = {
        "analysis_method": summary["analysis_method"],
        "comparison_direction": summary["contrast"]["direction"],
        "input_sample_count": qc_summary["sample_count"],
        "input_gene_count": qc_summary["gene_count"],
        "terminal_task_status": summary["status"],
        "statistical_test_performed": summary["statistical_test_performed"],
        "pvalue_available": summary["pvalue_available"],
        "adjusted_pvalue_available": summary["adjusted_pvalue_available"],
        "scientific_conclusion_generated": workflow[
            "scientific_conclusion_generated"
        ],
        "reliability_information": summary["reliability_information"],
        "warnings": summary["warnings"],
        "limitations": summary["limitations"],
        "interpretation_boundary": summary["interpretation_boundary"],
        "summary_fields": sorted(summary),
        "artifact_categories": [artifact["artifact_type"] for artifact in artifacts],
        "claims": [],
        "deseq2_execution_state": "not_requested",
    }
    comparison = compare_golden_result(
        observed, _golden(), environment={"deseq2_ready": False}
    )
    assert comparison["passed"] is True, comparison["failures"]
    assert set(_golden()["expected_summary_schema_fields"]).issubset(summary)
    assert summary["statistical_test_performed"] is False
    assert summary["pvalue_available"] is False
    assert summary["adjusted_pvalue_available"] is False
    assert "exploratory" in summary["interpretation_boundary"].lower()
