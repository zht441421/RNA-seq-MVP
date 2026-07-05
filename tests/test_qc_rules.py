from pathlib import Path

from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.services.qc_service import run_qc


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def example_config(project_id: str = "proj_qc_test") -> BulkRNASeqAnalysisConfig:
    return BulkRNASeqAnalysisConfig(
        project_id=project_id,
        count_matrix_file=str(EXAMPLES_DIR / "sample_count_matrix.csv"),
        metadata_file=str(EXAMPLES_DIR / "sample_metadata.csv"),
        sample_id_column="sample_id",
        gene_id_column="gene_id",
        group_column="group",
        reference_group="control",
        test_group="treatment",
        batch_column="batch",
        covariates=["age"],
    )


def test_qc_passes_example_files() -> None:
    report = run_qc(example_config())

    assert report.passed is True
    assert report.group_counts == {"control": 3, "treatment": 3}
    assert report.sample_alignment is not None
    assert report.sample_alignment.matched_sample_count == 6
    assert report.library_size_summary is not None
    assert report.low_count_gene_summary is not None


def test_qc_detects_negative_counts(tmp_path: Path) -> None:
    count_matrix = tmp_path / "counts.csv"
    metadata = tmp_path / "metadata.csv"
    count_matrix.write_text("gene_id,S1,S2\nGeneA,10,-1\n", encoding="utf-8")
    metadata.write_text("sample_id,group\nS1,control\nS2,treatment\n", encoding="utf-8")

    config = BulkRNASeqAnalysisConfig(
        project_id="proj_negative",
        count_matrix_file=str(count_matrix),
        metadata_file=str(metadata),
        sample_id_column="sample_id",
        gene_id_column="gene_id",
        group_column="group",
        reference_group="control",
        test_group="treatment",
    )
    report = run_qc(config)

    assert report.passed is False
    assert any(check.name == "count_values_non_negative" and check.status == "fail" for check in report.checks)


def test_qc_detects_sample_mismatch(tmp_path: Path) -> None:
    count_matrix = tmp_path / "counts.csv"
    metadata = tmp_path / "metadata.csv"
    count_matrix.write_text("gene_id,S1,S3\nGeneA,10,11\n", encoding="utf-8")
    metadata.write_text("sample_id,group\nS1,control\nS2,treatment\n", encoding="utf-8")

    config = BulkRNASeqAnalysisConfig(
        project_id="proj_mismatch",
        count_matrix_file=str(count_matrix),
        metadata_file=str(metadata),
        sample_id_column="sample_id",
        gene_id_column="gene_id",
        group_column="group",
        reference_group="control",
        test_group="treatment",
    )
    report = run_qc(config)

    assert report.passed is False
    assert any(check.name == "sample_ids_aligned" and check.status == "fail" for check in report.checks)

