import json
from pathlib import Path

from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.runners.r_bulk_rnaseq_runner import RBulkRNASeqRunner
from tests.test_qc_rules import example_config


def test_real_runner_generates_expected_analysis_config(tmp_path: Path) -> None:
    config = example_config("proj_real_config")
    plan = AnalysisPlan(
        project_id=config.project_id,
        design_formula="~ batch + age + group",
        fdr_threshold=0.01,
        log2fc_threshold=1.5,
    )
    runner = RBulkRNASeqRunner(rscript_executable="Rscript")

    analysis_config = runner.build_analysis_config(config=config, plan=plan, output_dir=tmp_path)

    assert analysis_config["project_id"] == "proj_real_config"
    assert analysis_config["count_matrix_path"].endswith("sample_count_matrix.csv")
    assert analysis_config["metadata_path"].endswith("sample_metadata.csv")
    assert analysis_config["gene_id_column"] == "gene_id"
    assert analysis_config["sample_id_column"] == "sample_id"
    assert analysis_config["group_column"] == "group"
    assert analysis_config["reference_group"] == "control"
    assert analysis_config["test_group"] == "treatment"
    assert analysis_config["batch_column"] == "batch"
    assert analysis_config["covariates"] == ["age"]
    assert analysis_config["fdr_threshold"] == 0.01
    assert analysis_config["log2fc_threshold"] == 1.5
    assert analysis_config["output_dir"] == str(tmp_path)


def test_real_runner_writes_analysis_config_json(tmp_path: Path) -> None:
    config = example_config("proj_real_config_write")
    plan = AnalysisPlan(project_id=config.project_id, design_formula="~ batch + age + group")
    runner = RBulkRNASeqRunner(rscript_executable="Rscript")
    analysis_config = runner.build_analysis_config(config=config, plan=plan, output_dir=tmp_path)

    config_path = runner.write_analysis_config(analysis_config, tmp_path)

    assert config_path == tmp_path / "09_environment" / "analysis_config.json"
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved == analysis_config


def test_real_runner_handles_missing_rscript(tmp_path: Path) -> None:
    config = example_config("proj_missing_rscript")
    plan = AnalysisPlan(project_id=config.project_id, design_formula="~ batch + age + group")
    runner = RBulkRNASeqRunner(rscript_executable="definitely_missing_Rscript_for_test")
    runner.default_output_dir = lambda project_id: tmp_path / project_id  # type: ignore[method-assign]

    result = runner.run(config=config, plan=plan)

    assert result["status"] == "failed"
    assert result["run_status"]["primary_method_status"] == "failed"
    assert result["run_status"]["validation_consistency_status"] == "rscript_unavailable"
    assert Path(result["run_status_path"]).exists()
