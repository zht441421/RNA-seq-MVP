from pathlib import Path

import pytest

from backend.app.services.contrast_validation import resolve_contrast
from backend.app.services.rnaseq_minimal import (
    CountMatrix,
    build_report_payload,
    compute_preliminary_log2fc,
    write_markdown_report,
)


def _metadata() -> list[dict]:
    return [
        {"sample_id": "sample_1", "condition": "control"},
        {"sample_id": "sample_2", "condition": "control"},
        {"sample_id": "sample_3", "condition": "treatment"},
        {"sample_id": "sample_4", "condition": "treatment"},
    ]


def _cpm_matrix() -> CountMatrix:
    return CountMatrix(
        gene_ids=["GeneA"],
        sample_ids=["sample_1", "sample_2", "sample_3", "sample_4"],
        values={
            "GeneA": {
                "sample_1": 10.0,
                "sample_2": 10.0,
                "sample_3": 30.0,
                "sample_4": 30.0,
            }
        },
        raw_total_counts={"GeneA": 80.0},
    )


def test_explicit_contrast_pins_minimal_log2fc_direction() -> None:
    metadata = _metadata()
    treatment_vs_control = resolve_contrast(
        metadata,
        contrast_column="condition",
        contrast_numerator="treatment",
        contrast_denominator="control",
    )
    control_vs_treatment = resolve_contrast(
        metadata,
        contrast_column="condition",
        contrast_numerator="control",
        contrast_denominator="treatment",
    )

    treatment_row = compute_preliminary_log2fc(
        _cpm_matrix(),
        metadata,
        treatment_vs_control,
    )[0]
    control_row = compute_preliminary_log2fc(
        _cpm_matrix(),
        metadata,
        control_vs_treatment,
    )[0]

    assert treatment_row["log2_fold_change"] > 0
    assert control_row["log2_fold_change"] < 0
    assert control_row["log2_fold_change"] == pytest.approx(
        -treatment_row["log2_fold_change"]
    )
    assert treatment_row["contrast_direction"] == "treatment_vs_control"
    assert treatment_row["positive_log2fc_interpretation"] == (
        "Higher in treatment relative to control"
    )
    assert treatment_row["negative_log2fc_interpretation"] == (
        "Lower in treatment relative to control"
    )


def test_inferred_contrast_remains_deterministic() -> None:
    metadata = _metadata()

    inferred = resolve_contrast(metadata)
    row = compute_preliminary_log2fc(_cpm_matrix(), metadata)[0]

    assert inferred.as_dict()["contrast_source"] == "inferred"
    assert inferred.as_dict()["direction"] == "treatment_vs_control"
    assert row["contrast_direction"] == "treatment_vs_control"
    assert row["log2_fold_change"] > 0


def test_minimal_report_includes_contrast_direction(tmp_path: Path) -> None:
    metadata = _metadata()
    contrast = resolve_contrast(
        metadata,
        contrast_column="condition",
        contrast_numerator="treatment",
        contrast_denominator="control",
    ).as_dict()
    rows = compute_preliminary_log2fc(_cpm_matrix(), metadata, resolve_contrast(metadata))
    payload = build_report_payload(
        task_id="task_contrast",
        execution_mode="minimal_real",
        metadata_file="demo/metadata.csv",
        count_matrix_file="demo/counts.csv",
        sample_count=4,
        gene_count=1,
        retained_gene_count_after_filtering=1,
        condition_counts={"control": 2, "treatment": 2},
        library_sizes={
            "sample_1": 100,
            "sample_2": 100,
            "sample_3": 100,
            "sample_4": 100,
        },
        min_total_count_filter=10,
        preliminary_rows=rows,
        contrast=contrast,
    )
    report_path = tmp_path / "report.md"

    write_markdown_report(report_path, payload)

    report_text = report_path.read_text(encoding="utf-8")
    assert "## Contrast direction" in report_text
    assert "`treatment_vs_control`" in report_text
    assert "Higher in treatment relative to control" in report_text
