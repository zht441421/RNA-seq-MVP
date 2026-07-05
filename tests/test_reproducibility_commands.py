from pathlib import Path

from tests.evidence_helpers import run_api_project
from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


def test_mock_reproducibility_command_files_exist() -> None:
    result = run_api_project(run_mode="mock")
    artifact_root: Path = result["artifact_root"]

    assert (artifact_root / "08_reproducible_code" / "run_command.txt").exists()
    assert (artifact_root / "08_reproducible_code" / "docker_command.txt").exists()
    assert "RUN_MODE=mock" in (artifact_root / "08_reproducible_code" / "run_command.txt").read_text(encoding="utf-8")


def test_docker_reproducibility_command_contains_docker_run() -> None:
    fixture = setup_completed_with_warning_project()
    artifact_root = Path(fixture["manifest"]["artifact_root"])
    command = (artifact_root / "08_reproducible_code" / "docker_command.txt").read_text(encoding="utf-8")

    assert "docker run --rm" in command
    assert "bioinformatics-agent-r-bulk-rnaseq:0.1" in command
    assert "Rscript backend/app/scripts/r/bulk_rnaseq_de.R" in command
    assert "09_environment/analysis_config.json" in command
