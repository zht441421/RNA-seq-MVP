from scripts.acceptance_phase_1 import (
    AcceptanceHttpError,
    bad_input_config,
    bad_input_smoke_passed,
    build_bad_input_files,
    summarize_bad_input_smoke,
)


def test_bad_input_files_and_config_are_generated(tmp_path) -> None:
    count_matrix, metadata = build_bad_input_files(tmp_path)
    config = bad_input_config("proj_bad", count_matrix, metadata)

    assert count_matrix.exists()
    assert metadata.exists()
    assert "-1" in count_matrix.read_text(encoding="utf-8")
    assert "S3" in metadata.read_text(encoding="utf-8")
    assert config["project_id"] == "proj_bad"
    assert config["count_matrix_file"] == str(count_matrix)
    assert config["metadata_file"] == str(metadata)


def test_bad_input_smoke_pass_helper_requires_structured_errors() -> None:
    qc = {
        "passed": False,
        "validation_issues": [
            {"code": "SAMPLE_ID_MISMATCH"},
            {"code": "COUNT_VALUES_NEGATIVE"},
        ],
    }
    run_error = AcceptanceHttpError(400, "POST", "/projects/proj_bad/run", '{"detail":"QC has blocking issues"}')
    results = {"strong_conclusion_allowed": False, "reliability_grade": None}

    summary = summarize_bad_input_smoke(qc=qc, run_error=run_error, results=results)

    assert summary["run_blocked"] is True
    assert summary["structured_validation_issues_returned"] is True
    assert bad_input_smoke_passed(summary) is True

