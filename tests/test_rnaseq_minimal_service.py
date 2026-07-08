import csv
import json
from pathlib import Path

import pytest

from backend.app.services.rnaseq_minimal import (
    build_report_payload,
    compute_cpm,
    compute_library_sizes,
    compute_preliminary_log2fc,
    filter_low_expression,
    format_markdown_table,
    read_count_matrix,
    read_metadata,
    summarize_top_ranked_genes,
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


def test_markdown_table_formatting_is_deterministic() -> None:
    rows = [
        {"gene_id": "GeneA", "log2_fold_change": "1.0000"},
        {"gene_id": "GeneB", "log2_fold_change": "-2.0000"},
    ]

    table = format_markdown_table(["gene_id", "log2_fold_change"], rows)

    assert table == "\n".join(
        [
            "| gene_id | log2_fold_change |",
            "| --- | --- |",
            "| GeneA | 1.0000 |",
            "| GeneB | -2.0000 |",
        ]
    )


def test_top_ranked_genes_are_sorted_by_absolute_log2fc_then_gene_id() -> None:
    rows = [
        {
            "gene_id": "GeneC",
            "mean_cpm_group_1": 1.23456,
            "mean_cpm_group_2": 2,
            "log2_fold_change": -2,
            "total_count": 20.0,
            "pvalue": 0.01,
        },
        {
            "gene_id": "GeneA",
            "mean_cpm_group_1": 3,
            "mean_cpm_group_2": 4.44444,
            "log2_fold_change": 2,
            "total_count": 10.5,
            "padj": 0.02,
        },
        {
            "gene_id": "GeneB",
            "mean_cpm_group_1": 5,
            "mean_cpm_group_2": 6,
            "log2_fold_change": 1,
            "total_count": 7,
            "qvalue": 0.03,
        },
    ]

    top_rows = summarize_top_ranked_genes(rows, limit=3)

    assert [row["gene_id"] for row in top_rows] == ["GeneA", "GeneC", "GeneB"]
    assert top_rows[0] == {
        "gene_id": "GeneA",
        "mean_cpm_group_1": "3.0000",
        "mean_cpm_group_2": "4.4444",
        "log2_fold_change": "2.0000",
        "total_count": "10.5000",
    }
    assert top_rows[1]["mean_cpm_group_1"] == "1.2346"
    assert top_rows[1]["total_count"] == "20"


def test_report_payload_uses_safe_paths_and_excludes_forbidden_statistical_fields() -> None:
    payload = build_report_payload(
        task_id="task_demo",
        execution_mode="minimal_real",
        metadata_file="D:\\private\\metadata.csv",
        count_matrix_file="/home/user/counts.csv",
        sample_count=2,
        gene_count=2,
        retained_gene_count_after_filtering=2,
        condition_counts={"control": 1, "treatment": 1},
        library_sizes={"sample_1": 100, "sample_2": 200},
        min_total_count_filter=10,
        generated_files=[
            {
                "name": "report.md",
                "relative_path": "C:\\private\\tasks\\task_demo\\report.md",
            }
        ],
        preliminary_rows=[
            {
                "gene_id": "GeneA",
                "mean_cpm_group_1": 10,
                "mean_cpm_group_2": 20,
                "log2_fold_change": 1,
                "total_count": 30,
                "pvalue": 0.01,
                "padj": 0.02,
                "qvalue": 0.03,
                "significant": True,
                "pathway": "ignored",
                "enrichment": "ignored",
            }
        ],
    )

    payload_text = json.dumps(payload, sort_keys=True).lower()

    assert payload["metadata_file"] == "metadata.csv"
    assert payload["count_matrix_file"] == "counts.csv"
    assert payload["generated_artifacts"][-1] == {
        "name": "report.md",
        "relative_path": "report.md",
    }
    for forbidden_fragment in (
        "pvalue",
        "padj",
        "qvalue",
        "significant",
        "pathway",
        "enrichment",
        "d:\\",
        "c:\\",
        "/home/",
    ):
        assert forbidden_fragment not in payload_text
