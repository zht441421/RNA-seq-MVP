import json
import subprocess
import sys
from pathlib import Path


EXAMPLES_DIR = Path("docs/examples/coze")
HELPER_SCRIPT = Path("scripts/print_phase_6_1_coze_contract_examples.py")
REQUIRED_EXAMPLE_FILES = (
    "create_task_request.json",
    "create_task_response.json",
    "register_metadata_request.json",
    "register_count_matrix_request.json",
    "run_minimal_contrast_request.json",
    "run_deseq2_contrast_request.json",
    "coze_summary_minimal_response.json",
    "artifact_download_reference.json",
    "error_invalid_contrast_response.json",
    "error_missing_input_response.json",
)
FORBIDDEN_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "traceback",
    "token",
    "password",
    "secret",
)


def _load_example(filename: str) -> object:
    return json.loads((EXAMPLES_DIR / filename).read_text(encoding="utf-8"))


def test_phase_6_1_coze_examples_exist_and_parse() -> None:
    assert EXAMPLES_DIR.is_dir()

    for filename in REQUIRED_EXAMPLE_FILES:
        path = EXAMPLES_DIR / filename
        assert path.is_file()
        json.loads(path.read_text(encoding="utf-8"))


def test_phase_6_1_coze_examples_include_key_contract_concepts() -> None:
    create_response = _load_example("create_task_response.json")
    metadata_register = _load_example("register_metadata_request.json")
    count_register = _load_example("register_count_matrix_request.json")
    minimal_run = _load_example("run_minimal_contrast_request.json")
    deseq2_run = _load_example("run_deseq2_contrast_request.json")
    summary = _load_example("coze_summary_minimal_response.json")
    download_reference = _load_example("artifact_download_reference.json")
    invalid_contrast = _load_example("error_invalid_contrast_response.json")
    missing_input = _load_example("error_missing_input_response.json")

    assert create_response["task_id"] == "task_0001"
    assert metadata_register["input_role"] == "metadata"
    assert count_register["input_role"] == "count_matrix"
    assert minimal_run["execution_mode"] == "minimal_real"
    assert minimal_run["analysis_method"] == "minimal_cpm_log2fc"
    assert minimal_run["contrast_column"] == "condition"
    assert minimal_run["contrast_numerator"] == "treatment"
    assert minimal_run["contrast_denominator"] == "control"
    assert deseq2_run["execution_mode"] == "formal_de_real"
    assert deseq2_run["analysis_method"] == "deseq2"
    assert deseq2_run["preflight_required"] is True
    assert summary["pvalue_available"] is False
    assert summary["download_links"]["report.md"].startswith("/task/task_0001/")
    assert download_reference["endpoint"].endswith("/download")
    assert invalid_contrast["detail"]["error_code"] == "CONTRAST_VALIDATION_FAILED"
    assert missing_input["detail"] == "Both metadata and count matrix inputs are required."


def test_phase_6_1_coze_examples_do_not_expose_forbidden_fragments() -> None:
    for filename in REQUIRED_EXAMPLE_FILES:
        text = (EXAMPLES_DIR / filename).read_text(encoding="utf-8").lower()
        for forbidden_fragment in FORBIDDEN_FRAGMENTS:
            assert forbidden_fragment not in text


def test_phase_6_1_helper_script_verifies_examples() -> None:
    result = subprocess.run(
        [sys.executable, str(HELPER_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Phase 6.1" in result.stdout
    assert "Coze contract examples verified" in result.stdout
