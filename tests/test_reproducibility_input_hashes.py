import json

from tests.evidence_helpers import run_api_project


def test_reproducibility_input_hashes_include_inputs_and_analysis_config_hash() -> None:
    result = run_api_project(run_mode="mock")
    path = result["artifact_root"] / "08_reproducible_code" / "input_hashes.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["count_matrix_path"]
    assert payload["count_matrix_sha256"]
    assert payload["metadata_path"]
    assert payload["metadata_sha256"]
    assert payload["analysis_config_sha256"]
