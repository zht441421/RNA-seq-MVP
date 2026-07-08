from pathlib import Path

import pytest

from backend.app.services.rnaseq_minimal import (
    CountMatrix,
    read_count_matrix,
    read_metadata,
    reorder_counts_to_metadata,
    validate_count_matrix,
    validate_metadata,
    validate_sample_alignment,
)


def _write_metadata(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "metadata.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_counts(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "counts.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _metadata_errors(tmp_path: Path, lines: list[str]) -> list[str]:
    return validate_metadata(read_metadata(_write_metadata(tmp_path, lines))).errors


def _count_errors(tmp_path: Path, lines: list[str]) -> list[str]:
    return validate_count_matrix(read_count_matrix(_write_counts(tmp_path, lines))).errors


def test_metadata_missing_sample_id_fails(tmp_path: Path) -> None:
    errors = _metadata_errors(
        tmp_path,
        [
            "condition",
            "control",
            "treatment",
        ],
    )

    assert any("sample_id" in error for error in errors)


def test_metadata_missing_condition_fails(tmp_path: Path) -> None:
    errors = _metadata_errors(
        tmp_path,
        [
            "sample_id",
            "sample_1",
            "sample_2",
        ],
    )

    assert any("condition" in error for error in errors)


def test_metadata_empty_file_fails(tmp_path: Path) -> None:
    path = tmp_path / "metadata.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="Metadata file must include a header row."):
        read_metadata(path)


def test_metadata_duplicate_sample_id_fails(tmp_path: Path) -> None:
    errors = _metadata_errors(
        tmp_path,
        [
            "sample_id,condition",
            "sample_1,control",
            "sample_1,treatment",
        ],
    )

    assert any("duplicate sample_id" in error for error in errors)


def test_metadata_empty_sample_id_fails(tmp_path: Path) -> None:
    errors = _metadata_errors(
        tmp_path,
        [
            "sample_id,condition",
            ",control",
            "sample_2,treatment",
        ],
    )

    assert any("empty sample_id" in error for error in errors)


def test_metadata_whitespace_only_fields_fail(tmp_path: Path) -> None:
    errors = _metadata_errors(
        tmp_path,
        [
            "sample_id,condition",
            "   ,control",
            "sample_2,   ",
        ],
    )

    assert any("empty sample_id" in error for error in errors)
    assert any("empty condition" in error for error in errors)


def test_metadata_fewer_than_two_samples_fails(tmp_path: Path) -> None:
    errors = _metadata_errors(
        tmp_path,
        [
            "sample_id,condition",
            "sample_1,control",
        ],
    )

    assert any("at least 2 distinct samples" in error for error in errors)


def test_metadata_only_one_condition_fails(tmp_path: Path) -> None:
    errors = _metadata_errors(
        tmp_path,
        [
            "sample_id,condition",
            "sample_1,control",
            "sample_2,control",
        ],
    )

    assert any("exactly 2 condition groups" in error for error in errors)


def test_metadata_more_than_two_conditions_fails(tmp_path: Path) -> None:
    errors = _metadata_errors(
        tmp_path,
        [
            "sample_id,condition",
            "sample_1,control",
            "sample_2,treatment",
            "sample_3,rescue",
        ],
    )

    assert any("more than 2 condition groups" in error for error in errors)


def test_counts_missing_gene_id_fails(tmp_path: Path) -> None:
    errors = _count_errors(
        tmp_path,
        [
            "feature_id,sample_1,sample_2",
            "GeneA,1,2",
        ],
    )

    assert "Count matrix first column must be gene_id." in errors


def test_counts_empty_file_fails(tmp_path: Path) -> None:
    path = tmp_path / "counts.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="Count matrix file must include a header row."):
        read_count_matrix(path)


def test_counts_duplicate_gene_id_fails(tmp_path: Path) -> None:
    errors = _count_errors(
        tmp_path,
        [
            "gene_id,sample_1,sample_2",
            "GeneA,1,2",
            "GeneA,3,4",
        ],
    )

    assert any("duplicate gene_id" in error for error in errors)


def test_counts_empty_gene_id_fails(tmp_path: Path) -> None:
    errors = _count_errors(
        tmp_path,
        [
            "gene_id,sample_1,sample_2",
            ",1,2",
        ],
    )

    assert any("empty gene_id" in error for error in errors)


def test_counts_whitespace_only_gene_id_fails(tmp_path: Path) -> None:
    errors = _count_errors(
        tmp_path,
        [
            "gene_id,sample_1,sample_2",
            "   ,1,2",
        ],
    )

    assert any("empty gene_id" in error for error in errors)


def test_counts_non_numeric_value_fails(tmp_path: Path) -> None:
    path = _write_counts(
        tmp_path,
        [
            "gene_id,sample_1,sample_2",
            "GeneA,1,not_a_number",
        ],
    )

    with pytest.raises(ValueError, match="non-numeric count value"):
        read_count_matrix(path)


def test_counts_negative_value_fails(tmp_path: Path) -> None:
    errors = _count_errors(
        tmp_path,
        [
            "gene_id,sample_1,sample_2",
            "GeneA,1,-2",
        ],
    )

    assert any("negative count" in error for error in errors)


def test_counts_missing_value_fails(tmp_path: Path) -> None:
    path = _write_counts(
        tmp_path,
        [
            "gene_id,sample_1,sample_2",
            "GeneA,1,",
        ],
    )

    with pytest.raises(ValueError, match="empty count value"):
        read_count_matrix(path)


def test_counts_duplicate_sample_columns_fail(tmp_path: Path) -> None:
    errors = _count_errors(
        tmp_path,
        [
            "gene_id,sample_1,sample_1",
            "GeneA,1,2",
        ],
    )

    assert any("duplicate sample columns" in error for error in errors)


def test_counts_sample_mismatch_extra_sample_fails(tmp_path: Path) -> None:
    metadata = read_metadata(
        _write_metadata(
            tmp_path,
            [
                "sample_id,condition",
                "sample_1,control",
                "sample_2,treatment",
            ],
        )
    )
    counts = read_count_matrix(
        _write_counts(
            tmp_path,
            [
                "gene_id,sample_1,sample_2,sample_3",
                "GeneA,1,2,3",
            ],
        )
    )

    errors = validate_sample_alignment(metadata, counts).errors

    assert any("sample_3" in error for error in errors)


def test_counts_sample_mismatch_missing_sample_fails(tmp_path: Path) -> None:
    metadata = read_metadata(
        _write_metadata(
            tmp_path,
            [
                "sample_id,condition",
                "sample_1,control",
                "sample_2,treatment",
            ],
        )
    )
    counts = read_count_matrix(
        _write_counts(
            tmp_path,
            [
                "gene_id,sample_1",
                "GeneA,1",
            ],
        )
    )

    errors = validate_sample_alignment(metadata, counts).errors

    assert any("sample_2" in error for error in errors)


def test_zero_library_size_sample_fails(tmp_path: Path) -> None:
    errors = _count_errors(
        tmp_path,
        [
            "gene_id,sample_1,sample_2",
            "GeneA,1,0",
            "GeneB,2,0",
        ],
    )

    assert any("zero library size" in error for error in errors)


def test_sample_column_order_can_be_aligned_to_metadata_order(tmp_path: Path) -> None:
    metadata = read_metadata(
        _write_metadata(
            tmp_path,
            [
                "sample_id,condition",
                "sample_1,control",
                "sample_2,treatment",
            ],
        )
    )
    counts = read_count_matrix(
        _write_counts(
            tmp_path,
            [
                "gene_id,sample_2,sample_1",
                "GeneA,20,10",
            ],
        )
    )

    alignment = validate_sample_alignment(metadata, counts)
    reordered = reorder_counts_to_metadata(metadata, counts)

    assert alignment.valid is True
    assert alignment.warnings == [
        "Metadata sample order differs from count matrix; samples were matched by ID."
    ]
    assert reordered.sample_ids == ["sample_1", "sample_2"]
    assert reordered.values["GeneA"] == {"sample_1": 10, "sample_2": 20}


def test_validation_detects_missing_values_in_in_memory_matrix() -> None:
    counts = CountMatrix(
        gene_ids=["GeneA"],
        sample_ids=["sample_1", "sample_2"],
        values={"GeneA": {"sample_1": 1}},
    )

    errors = validate_count_matrix(counts).errors

    assert any("missing a value" in error for error in errors)
