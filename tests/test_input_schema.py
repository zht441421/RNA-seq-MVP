import pytest
from pydantic import ValidationError

from backend.app.models.schemas import BulkRNASeqAnalysisConfig, InputLevel, OmicsType


def valid_payload() -> dict:
    return {
        "project_id": "proj_test",
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "count_matrix_file": "examples/sample_count_matrix.csv",
        "metadata_file": "examples/sample_metadata.csv",
        "sample_id_column": "sample_id",
        "gene_id_column": "gene_id",
        "group_column": "group",
        "reference_group": "control",
        "test_group": "treatment",
        "batch_column": "batch",
        "covariates": ["age"],
        "organism": "human",
        "gene_id_type": "symbol",
        "annotation_version": "mock",
        "fdr_threshold": 0.05,
        "log2fc_threshold": 1.0,
        "validation_methods": ["edgeR", "limma_voom"],
    }


def test_bulk_rnaseq_config_accepts_valid_payload() -> None:
    config = BulkRNASeqAnalysisConfig(**valid_payload())

    assert config.omics_type == OmicsType.BULK_RNASEQ
    assert config.input_level == InputLevel.COUNT_MATRIX
    assert config.validation_methods == ["edgeR", "limma_voom"]


def test_bulk_rnaseq_config_rejects_invalid_fdr() -> None:
    payload = valid_payload()
    payload["fdr_threshold"] = 1.5

    with pytest.raises(ValidationError):
        BulkRNASeqAnalysisConfig(**payload)


def test_bulk_rnaseq_config_requires_contrast_groups() -> None:
    payload = valid_payload()
    payload.pop("reference_group")

    with pytest.raises(ValidationError):
        BulkRNASeqAnalysisConfig(**payload)

