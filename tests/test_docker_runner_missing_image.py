import subprocess

from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.runners.docker_r_bulk_rnaseq_runner import DockerRBulkRNASeqRunner
from tests.test_qc_rules import example_config


def test_docker_runner_missing_image_returns_structured_failure(monkeypatch, tmp_path) -> None:
    def fake_run(command, capture_output, text, check):
        if command[:2] == ["docker", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="24.0.0", stderr="")
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="No such image")
        raise AssertionError(command)

    monkeypatch.setattr(subprocess, "run", fake_run)
    config = example_config("proj_missing_image")
    plan = AnalysisPlan(project_id=config.project_id, design_formula="~ batch + age + group")
    runner = DockerRBulkRNASeqRunner(docker_executable="docker", image_name="missing:latest")
    runner.default_output_dir = lambda project_id: runner.project_root / "artifacts" / f"test_{project_id}"  # type: ignore[method-assign]

    result = runner.run(config=config, plan=plan)

    assert result["status"] == "failed"
    assert result["run_status"]["primary_method_status"] == "failed"
    assert result["run_status"]["validation_consistency_status"] == "docker_image_unavailable"
    assert result["docker_available"] is True
