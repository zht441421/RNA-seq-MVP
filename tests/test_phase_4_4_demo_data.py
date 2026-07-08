import csv
from collections import Counter
from pathlib import Path


DEMO_DIR = Path("data/demo/rnaseq_minimal")
FORBIDDEN_DEMO_FRAGMENTS = (
    "pvalue",
    "padj",
    "qvalue",
    "significant",
    "enrichment",
    "pathway",
)


def test_phase_4_4_demo_metadata_and_counts_are_valid() -> None:
    metadata_path = DEMO_DIR / "metadata.csv"
    counts_path = DEMO_DIR / "counts.csv"

    assert metadata_path.is_file()
    assert counts_path.is_file()

    with metadata_path.open("r", encoding="utf-8", newline="") as metadata_file:
        metadata_rows = list(csv.DictReader(metadata_file))

    with counts_path.open("r", encoding="utf-8", newline="") as counts_file:
        counts_reader = csv.DictReader(counts_file)
        count_rows = list(counts_reader)
        count_columns = counts_reader.fieldnames or []

    assert {"sample_id", "condition"}.issubset(metadata_rows[0].keys())
    assert count_columns[0] == "gene_id"

    metadata_samples = [row["sample_id"] for row in metadata_rows]
    count_samples = count_columns[1:]
    assert metadata_samples == count_samples

    condition_counts = Counter(row["condition"] for row in metadata_rows)
    assert set(condition_counts) == {"control", "treatment"}
    assert all(sample_count >= 2 for sample_count in condition_counts.values())

    has_low_count_gene = False
    for row in count_rows:
        total_count = 0
        for sample_id in count_samples:
            value = row[sample_id]
            assert value.isdigit()
            total_count += int(value)
        has_low_count_gene = has_low_count_gene or total_count < 10

    assert has_low_count_gene


def test_phase_4_4_demo_files_do_not_contain_forbidden_result_claims() -> None:
    for path in (
        DEMO_DIR / "metadata.csv",
        DEMO_DIR / "counts.csv",
        DEMO_DIR / "README.md",
    ):
        assert path.is_file()
        text = path.read_text(encoding="utf-8").lower()
        for forbidden_fragment in FORBIDDEN_DEMO_FRAGMENTS:
            assert forbidden_fragment not in text
