from pathlib import Path

from tests.evidence_helpers import manifest_entry, run_api_project
from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


REPRO_FILES = [
    "08_reproducible_code/README_REPRODUCE.md",
    "08_reproducible_code/analysis_config.json",
    "08_reproducible_code/run_command.txt",
    "08_reproducible_code/docker_command.txt",
    "08_reproducible_code/input_hashes.json",
    "08_reproducible_code/software_versions.json",
]


def test_mock_run_generates_reproducibility_bundle() -> None:
    result = run_api_project(run_mode="mock")
    artifact_root: Path = result["artifact_root"]
    manifest = result["manifest"]

    for relative_path in REPRO_FILES:
        assert (artifact_root / relative_path).exists()
        assert manifest_entry(manifest, relative_path)["status"] == "present"

    readme = (artifact_root / "08_reproducible_code" / "README_REPRODUCE.md").read_text(encoding="utf-8")
    assert "Replay is intended to reproduce the computational workflow" in readme
    assert "Reliability grade" in readme


def test_docker_like_run_generates_reproducibility_bundle() -> None:
    fixture = setup_completed_with_warning_project()
    artifact_root = Path(fixture["manifest"]["artifact_root"])

    for relative_path in REPRO_FILES:
        assert (artifact_root / relative_path).exists()

    software_versions = (artifact_root / "08_reproducible_code" / "software_versions.json").read_text(encoding="utf-8")
    assert "docker_r" in software_versions
    assert "bioinformatics-agent-r-bulk-rnaseq:0.1" in software_versions
