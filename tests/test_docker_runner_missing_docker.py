from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.runners.docker_r_bulk_rnaseq_runner import DockerRBulkRNASeqRunner
from tests.test_qc_rules import example_config


def test_docker_runner_missing_docker_returns_structured_failure(tmp_path) -> None:
    config = example_config("proj_missing_docker")
    plan = AnalysisPlan(project_id=config.project_id, design_formula="~ batch + age + group")
    runner = DockerRBulkRNASeqRunner(
        docker_executable="definitely_missing_docker_for_runner_test",
        image_name="bioinformatics-agent-r-bulk-rnaseq:0.1",
    )
    runner.default_output_dir = lambda project_id: runner.project_root / "artifacts" / f"test_{project_id}"  # type: ignore[method-assign]

    result = runner.run(config=config, plan=plan)

    assert result["status"] == "failed"
    assert result["mode"] == "docker_r"
    assert result["run_status"]["primary_method_status"] == "failed"
    assert result["run_status"]["validation_consistency_status"] == "docker_unavailable"
    assert result["docker_available"] is False
