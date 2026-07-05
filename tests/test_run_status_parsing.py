import json
from pathlib import Path

from backend.app.runners.r_bulk_rnaseq_runner import parse_run_status


def test_parse_run_status_reads_valid_json(tmp_path: Path) -> None:
    run_status_path = tmp_path / "run_status.json"
    payload = {
        "execution_mode": "real_r",
        "primary_method_status": "completed",
        "validation_method_status": {"edgeR": "completed", "limma_voom": "skipped"},
        "validation_consistency_score": 0.75,
        "fdr_applied": True,
    }
    run_status_path.write_text(json.dumps(payload), encoding="utf-8")

    parsed = parse_run_status(run_status_path)

    assert parsed["primary_method_status"] == "completed"
    assert parsed["validation_method_status"]["edgeR"] == "completed"


def test_parse_run_status_handles_missing_file(tmp_path: Path) -> None:
    parsed = parse_run_status(tmp_path / "missing_run_status.json")

    assert parsed["primary_method_status"] == "failed"
    assert parsed["validation_consistency_status"] == "missing_run_status"
    assert parsed["errors"]


def test_parse_run_status_handles_invalid_json(tmp_path: Path) -> None:
    run_status_path = tmp_path / "run_status.json"
    run_status_path.write_text("{not-json", encoding="utf-8")

    parsed = parse_run_status(run_status_path)

    assert parsed["primary_method_status"] == "failed"
    assert parsed["validation_consistency_status"] == "invalid_run_status"
    assert parsed["errors"]

