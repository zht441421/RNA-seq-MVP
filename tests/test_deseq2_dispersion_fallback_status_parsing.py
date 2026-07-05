import json
from pathlib import Path

from backend.app.runners.r_bulk_rnaseq_runner import is_primary_method_success, parse_run_status


def test_parse_run_status_preserves_deseq2_dispersion_fallback_warning(tmp_path: Path) -> None:
    run_status_path = tmp_path / "run_status.json"
    payload = {
        "execution_mode": "docker_r",
        "primary_method_status": "completed_with_warning",
        "validation_method_status": {"edgeR": "completed", "limma_voom": "completed"},
        "validation_consistency_score": 0.86,
        "validation_consistency_status": "computed",
        "fdr_applied": True,
        "warnings": [
            "DESeq2 standard dispersion fit failed; used gene-wise dispersion fallback.",
        ],
    }
    run_status_path.write_text(json.dumps(payload), encoding="utf-8")

    parsed = parse_run_status(run_status_path)

    assert parsed["primary_method_status"] == "completed_with_warning"
    assert is_primary_method_success(parsed) is True
    assert "gene-wise dispersion fallback" in parsed["warnings"][0]
