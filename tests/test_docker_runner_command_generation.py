from pathlib import Path

from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.runners.docker_r_bulk_rnaseq_runner import DockerRBulkRNASeqRunner
from tests.test_qc_rules import example_config


def test_docker_runner_generates_container_paths_and_command(tmp_path: Path) -> None:
    config = example_config("proj_docker_command")
    plan = AnalysisPlan(project_id=config.project_id, design_formula="~ batch + age + group")
    runner = DockerRBulkRNASeqRunner(
        docker_executable="docker",
        image_name="bioinformatics-agent-r-bulk-rnaseq:0.1",
        docker_workdir="/workspace",
    )
    output_dir = runner.default_output_dir(config.project_id)

    analysis_config = runner.build_analysis_config(config=config, plan=plan, output_dir=output_dir)
    config_path = runner.write_analysis_config(analysis_config, output_dir)
    command = runner.build_docker_command(config_path)

    assert analysis_config["count_matrix_path"].startswith("/workspace/")
    assert analysis_config["metadata_path"].startswith("/workspace/")
    assert analysis_config["output_dir"].startswith("/workspace/artifacts/")
    assert command[:3] == ["docker", "run", "--rm"]
    assert "-v" in command
    assert "bioinformatics-agent-r-bulk-rnaseq:0.1" in command
    assert command[-3:] == [
        "Rscript",
        "backend/app/scripts/r/bulk_rnaseq_de.R",
        analysis_config["output_dir"] + "/09_environment/analysis_config.json",
    ]

