import csv
from pathlib import Path

import pytest

from backend.app.services.rnaseq_minimal import (
    compute_cpm,
    compute_library_sizes,
    compute_preliminary_log2fc,
    filter_low_expression,
    read_count_matrix,
    read_metadata,
    validate_count_matrix,
    validate_metadata,
    validate_sample_alignment,
)


def _metadata_path(tmp_path: Path) -> Path:
    path = tmp_path / "metadata.csv"
    path.write_text(
        "\n".join(
            [
                "sample_id,condition",
                "sample_1,control",
                "sample_2,control",
                "sample_3,treatment",
                "sample_4,treatment",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _counts_path(tmp_path: Path) -> Path:
    path = tmp_path / "counts.csv"
    path.write_text(
        "\n".join(
            [
                "gene_id,sample_1,sample_2,sample_3,sample_4",
                "GeneA,100,120,250,260",
                "GeneB,5,3,4,6",
                "GeneC,1,1,0,0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_metadata_parsing_and_validation(tmp_path: Path) -> None:
    metadata = read_metadata(_metadata_path(tmp_path))

    assert metadata == [
        {"sample_id": "sample_1", "condition": "control"},
        {"sample_id": "sample_2", "condition": "control"},
        {"sample_id": "sample_3", "condition": "treatment"},
        {"sample_id": "sample_4", "condition": "treatment"},
    ]
    assert validate_metadata(metadata).valid is True


def test_count_matrix_parsing_and_validation(tmp_path: Path) -> None:
    counts = read_count_matrix(_counts_path(tmp_path))

    assert counts.gene_id_column == "gene_id"
    assert counts.sample_ids == ["sample_1", "sample_2", "sample_3", "sample_4"]
    assert counts.gene_ids == ["GeneA", "GeneB", "GeneC"]
    assert counts.values["GeneA"]["sample_1"] == 100
    assert validate_count_matrix(counts).valid is True


def test_sample_alignment_success(tmp_path: Path) -> None:
    metadata = read_metadata(_metadata_path(tmp_path))
    counts = read_count_matrix(_counts_path(tmp_path))

    result = validate_sample_alignment(metadata, counts)

    assert result.valid is True
    assert result.errors == []


def test_sample_alignment_failure(tmp_path: Path) -> None:
    metadata = read_metadata(_metadata_path(tmp_path))
    mismatched_counts_path = tmp_path / "counts_mismatched.csv"
    mismatched_counts_path.write_text(
        "\n".join(
            [
                "gene_id,sample_1,sample_2,sample_3,sample_missing",
                "GeneA,100,120,250,260",
                "",
            ]
        ),
        encoding="utf-8",
    )
    counts = read_count_matrix(mismatched_counts_path)

    result = validate_sample_alignment(metadata, counts)

    assert result.valid is False
    assert any("sample_4" in error for error in result.errors)
    assert any("sample_missing" in error for error in result.errors)


def test_library_size_and_cpm_computation(tmp_path: Path) -> None:
    counts = read_count_matrix(_counts_path(tmp_path))

    library_sizes = compute_library_sizes(counts)
    cpm = compute_cpm(counts)

    assert library_sizes == {
        "sample_1": 106,
        "sample_2": 124,
        "sample_3": 254,
        "sample_4": 266,
    }
    assert cpm.values["GeneA"]["sample_1"] == pytest.approx(943396.2264)
    assert cpm.raw_total_counts["GeneA"] == 730


def test_low_expression_filtering(tmp_path: Path) -> None:
    counts = read_count_matrix(_counts_path(tmp_path))

    filtered = filter_low_expression(counts, min_total_count=10)

    assert filtered.gene_ids == ["GeneA", "GeneB"]
    assert "GeneC" not in filtered.values


def test_preliminary_log2fc_output_does_not_include_significance_fields(
    tmp_path: Path,
) -> None:
    metadata = read_metadata(_metadata_path(tmp_path))
    cpm = compute_cpm(read_count_matrix(_counts_path(tmp_path)))
    filtered_cpm = filter_low_expression(cpm, min_total_count=10)

    rows = compute_preliminary_log2fc(filtered_cpm, metadata)

    assert rows
    forbidden_fields = {"pvalue", "padj", "qvalue"}
    assert all(forbidden_fields.isdisjoint(row.keys()) for row in rows)
    assert all("Preliminary ranking only" in row["analysis_note"] for row in rows)
