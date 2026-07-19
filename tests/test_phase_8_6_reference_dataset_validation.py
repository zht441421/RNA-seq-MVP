from __future__ import annotations

import copy
import math
from pathlib import Path

from backend.app.services.reference_validation import (
    compare_golden_result,
    load_json_object,
    validate_golden_result,
    validate_reference_manifest,
)
from scripts.phase_8_6_reference_common import ReferenceDataError, public_datasets, select_datasets
from scripts.phase_8_6_reference_common import verify_artifact
from scripts.verify_phase_8_6_reference_dataset_validation import verify_structure


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/reference-datasets/reference-dataset-manifest.json"


def _manifest() -> dict:
    return load_json_object(MANIFEST)


def _golden(dataset_id: str) -> dict:
    dataset = next(item for item in _manifest()["datasets"] if item["dataset_id"] == dataset_id)
    return load_json_object(ROOT / dataset["golden_result"])


def test_phase_8_6_declares_two_independent_real_public_datasets() -> None:
    manifest = _manifest()
    assert validate_reference_manifest(manifest, repository_root=ROOT, verify_local_files=True) == []
    datasets = public_datasets(manifest)
    assert {item["dataset_id"] for item in datasets} == {
        "phase-8-6-pasilla-public-v1",
        "phase-8-6-gse60450-luminal-public-v1",
    }
    assert {item["provenance"]["organism"] for item in datasets} == {
        "Drosophila melanogaster", "Mus musculus"
    }
    assert all(item["retrieval"]["credentials_required"] is False for item in datasets)


def test_real_public_manifest_requires_provenance_and_usage_fields() -> None:
    manifest = copy.deepcopy(_manifest())
    public_datasets(manifest)[0].pop("citation")
    errors = validate_reference_manifest(manifest)
    assert any("missing real-public fields" in error and "citation" in error for error in errors)


def test_dataset_selection_is_explicit_and_rejects_unknown_ids() -> None:
    selected = select_datasets("phase-8-6-pasilla-public-v1", all_datasets=False, manifest=_manifest())
    assert [item["dataset_id"] for item in selected] == ["phase-8-6-pasilla-public-v1"]
    try:
        select_datasets("unknown", all_datasets=False, manifest=_manifest())
    except ReferenceDataError as exc:
        assert "not declared" in str(exc)
    else:
        raise AssertionError("unknown dataset must be rejected")


def test_source_artifact_checksum_tampering_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "source.bin"
    path.write_bytes(b"actual public bytes")
    artifact = {"size_bytes": path.stat().st_size, "sha256": "0" * 64}
    try:
        verify_artifact(path, artifact)
    except ReferenceDataError as exc:
        assert "checksum" in str(exc)
    else:
        raise AssertionError("tampered source checksum must be rejected")


def test_real_public_golden_results_use_tolerances_and_scientific_boundaries() -> None:
    for dataset in public_datasets(_manifest()):
        golden = _golden(dataset["dataset_id"])
        assert validate_golden_result(golden) == []
        assert golden["checks"]["numeric_tolerances"]
        assert golden["checks"]["overlap_thresholds"]
        assert golden["checks"]["finite_fields"]
        assert golden["scientific_boundaries"]["golden_result_validates"] == "system_behavior_not_biological_truth"
        assert golden["scientific_boundaries"]["statistical_significance_claims_allowed"] is False


def test_golden_comparison_rejects_nonfinite_values_without_crashing() -> None:
    golden = _golden("phase-8-6-pasilla-public-v1")
    observed = {
        **golden["checks"]["exact"],
        "retained_gene_count": 9921,
        "reliability_information": {"available": False, "grade": None, "strong_conclusion_allowed": False},
        "warnings": [], "limitations": [], "interpretation_boundary": "Exploratory, not formal.",
        "summary_fields": [], "artifact_categories": golden["checks"]["required_artifact_categories"],
        "claims": [], "deseq2_execution_state": "unavailable",
        "selected_gene_log2fc": {"FBgn0039155": math.nan},
        "top_ranked_gene_ids": golden["checks"]["overlap_thresholds"]["top_ranked_gene_ids"]["expected"],
        "ranking_log2fc_values": [math.inf],
    }
    comparison = compare_golden_result(observed, golden, environment={"deseq2_ready": False})
    assert comparison["passed"] is False
    assert any("finite" in failure or "numeric_tolerance" in failure for failure in comparison["failures"])


def test_phase_8_6_structure_and_offline_compatibility_gate_passes() -> None:
    assert verify_structure() == []
