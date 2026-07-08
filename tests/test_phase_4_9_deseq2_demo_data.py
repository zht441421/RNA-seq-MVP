import csv
from collections import Counter
from pathlib import Path


DEMO_DIR = Path("data/demo/deseq2_minimal")


def test_phase_4_9_deseq2_demo_files_exist_and_are_documented() -> None:
    metadata_path = DEMO_DIR / "metadata.csv"
    counts_path = DEMO_DIR / "counts.csv"
    readme_path = DEMO_DIR / "README.md"

    assert metadata_path.is_file()
    assert counts_path.is_file()
    assert readme_path.is_file()

    readme = readme_path.read_text(encoding="utf-8").lower()
    assert "synthetic demo data" in readme
    assert "not for biological interpretation" in readme
    assert "pipeline validation only" in readme


def test_phase_4_9_deseq2_demo_metadata_and_counts_are_valid() -> None:
    metadata_path = DEMO_DIR / "metadata.csv"
    counts_path = DEMO_DIR / "counts.csv"

    with metadata_path.open("r", encoding="utf-8", newline="") as metadata_file:
        metadata_rows = list(csv.DictReader(metadata_file))

    with counts_path.open("r", encoding="utf-8", newline="") as counts_file:
        counts_reader = csv.DictReader(counts_file)
        count_rows = list(counts_reader)
        count_columns = counts_reader.fieldnames or []

    assert metadata_rows
    assert {"sample_id", "condition"}.issubset(metadata_rows[0].keys())

    sample_ids = [row["sample_id"] for row in metadata_rows]
    assert len(sample_ids) >= 6
    assert all(sample_ids)
    assert len(sample_ids) == len(set(sample_ids))

    condition_counts = Counter(row["condition"] for row in metadata_rows)
    assert set(condition_counts) == {"control", "treated"}
    assert all(sample_count == 3 for sample_count in condition_counts.values())

    assert count_columns
    assert count_columns[0] == "gene_id"
    count_samples = count_columns[1:]
    assert count_samples == sample_ids

    assert 8 <= len(count_rows) <= 20
    gene_ids = [row["gene_id"] for row in count_rows]
    assert all(gene_ids)
    assert len(gene_ids) == len(set(gene_ids))

    library_sizes = {sample_id: 0 for sample_id in count_samples}
    for row in count_rows:
        for sample_id in count_samples:
            value = row[sample_id]
            assert value.isdigit()
            count = int(value)
            assert count >= 0
            library_sizes[sample_id] += count

    assert all(library_size > 0 for library_size in library_sizes.values())
