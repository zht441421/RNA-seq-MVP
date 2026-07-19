"""Shared deterministic Phase 8.6 reference-data operations.

This module handles public-file retrieval and format conversion only. It does
not implement or alter RNA-seq analysis.
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile
import tempfile
from typing import Any, Iterable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.reference_validation import load_json_object, sha256_file


MANIFEST_PATH = ROOT / "docs/reference-datasets/reference-dataset-manifest.json"
PREPROCESSING_VERSION = "phase-8-6-preprocess-v1"


class ReferenceDataError(RuntimeError):
    pass


def load_manifest() -> dict[str, Any]:
    return load_json_object(MANIFEST_PATH)


def public_datasets(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    value = manifest or load_manifest()
    return [
        dataset
        for dataset in value.get("datasets", [])
        if dataset.get("classification") == "reference_dataset"
        and dataset.get("data_nature") == "real_public"
    ]


def select_datasets(
    dataset_id: str | None,
    *,
    all_datasets: bool,
    manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    datasets = public_datasets(manifest)
    if all_datasets:
        return datasets
    if dataset_id:
        selected = [item for item in datasets if item.get("dataset_id") == dataset_id]
        if not selected:
            raise ReferenceDataError("Requested public reference dataset is not declared.")
        return selected
    raise ReferenceDataError("Select one dataset or use --all.")


def repository_path(relative: str) -> Path:
    posix = PurePosixPath(str(relative).replace("\\", "/"))
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise ReferenceDataError("Manifest contains an unsafe relative path.")
    return ROOT / Path(*posix.parts)


def cache_artifact_path(artifact: dict[str, Any]) -> Path:
    return repository_path(f".reference-data/cache/{artifact['cache_path']}")


def prepared_dataset_root(dataset: dict[str, Any]) -> Path:
    return repository_path(f".reference-data/prepared/{dataset['dataset_id']}")


def verify_artifact(path: Path, artifact: dict[str, Any]) -> None:
    if not path.is_file():
        raise ReferenceDataError("Declared public source file is not cached.")
    if path.stat().st_size != int(artifact["size_bytes"]):
        raise ReferenceDataError("Cached public source size does not match the manifest.")
    if sha256_file(path).lower() != str(artifact["sha256"]).lower():
        raise ReferenceDataError("Cached public source checksum does not match the manifest.")


def fetch_dataset(
    dataset: dict[str, Any], *, dry_run: bool = False, cache_only: bool = False
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for artifact in dataset["retrieval"]["artifacts"]:
        path = cache_artifact_path(artifact)
        cached = path.is_file()
        if cached:
            verify_artifact(path, artifact)
            status = "verified_cache"
        elif dry_run:
            status = "would_download"
        elif cache_only:
            raise ReferenceDataError("Required public source is absent in cache-only mode.")
        else:
            _download_artifact(artifact, path)
            verify_artifact(path, artifact)
            status = "downloaded_and_verified"
        results.append(
            {
                "dataset_id": dataset["dataset_id"],
                "source": artifact["url"],
                "size_bytes": artifact["size_bytes"],
                "sha256": artifact["sha256"],
                "cache_status": status,
                "cache_reference": artifact["cache_path"],
            }
        )
    return results


def _download_artifact(artifact: dict[str, Any], destination: Path) -> None:
    parsed = urlsplit(str(artifact.get("url") or ""))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ReferenceDataError("Public retrieval URL must be credential-free HTTPS.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(artifact["url"], headers={"User-Agent": "bioinformatics-agent-phase-8-6/1"})
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as target:
            temporary = Path(target.name)
            with urlopen(request, timeout=60) as response:
                shutil.copyfileobj(response, target, length=1024 * 1024)
        temporary.replace(destination)
    except Exception as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise ReferenceDataError("Public reference download failed safely.") from exc


def prepare_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    for artifact in dataset["retrieval"]["artifacts"]:
        verify_artifact(cache_artifact_path(artifact), artifact)
    adapter = dataset["preprocessing"]["adapter"]
    if adapter == "pasilla_bioconductor_tar":
        metadata, counts = _prepare_pasilla(dataset)
    elif adapter == "gse60450_geo_counts":
        metadata, counts = _prepare_gse60450(dataset)
    else:
        raise ReferenceDataError("Unsupported declared preprocessing adapter.")

    sample_order = list(dataset["preprocessing"]["sample_order"])
    metadata_by_sample = {row["sample_id"]: row for row in metadata}
    if set(metadata_by_sample) != set(sample_order):
        raise ReferenceDataError("Prepared metadata samples do not match the declared order.")
    ordered_metadata = [metadata_by_sample[sample] for sample in sample_order]
    output_root = prepared_dataset_root(dataset)
    output_root.mkdir(parents=True, exist_ok=True)
    metadata_path = output_root / "metadata.csv"
    counts_path = output_root / "counts.csv"
    _write_csv(metadata_path, ordered_metadata, ["sample_id", "condition", "source_accession", "source_label"])
    _write_counts(counts_path, counts, sample_order)
    checksums = {
        "metadata": sha256_file(metadata_path),
        "count_matrix": sha256_file(counts_path),
    }
    _verify_prepared_checksums(dataset, checksums)
    provenance = {
        "schema_version": "1.0",
        "dataset_id": dataset["dataset_id"],
        "source_version": dataset["source_version"],
        "source_checksums": {
            artifact["name"]: artifact["sha256"]
            for artifact in dataset["retrieval"]["artifacts"]
        },
        "preprocessing_version": PREPROCESSING_VERSION,
        "policies": {
            key: dataset["preprocessing"][key]
            for key in (
                "gene_order", "duplicate_gene_policy", "missing_value_policy",
                "non_integer_count_policy", "zero_count_gene_policy", "biological_filtering",
            )
        },
        "sample_order": sample_order,
        "sample_count": len(sample_order),
        "gene_count": len(counts),
        "prepared_checksums": checksums,
    }
    (output_root / "preprocessing-provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return provenance


def _prepare_pasilla(dataset: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    archive = cache_artifact_path(dataset["retrieval"]["artifacts"][0])
    members = dataset["preprocessing"]["source_members"]
    with tarfile.open(archive, "r:gz") as source:
        counts_text = _tar_text(source, members["count_matrix"])
        metadata_text = _tar_text(source, members["metadata"])
    metadata_rows = list(csv.DictReader(metadata_text.splitlines()))
    metadata: list[dict[str, str]] = []
    for row in metadata_rows:
        raw_id = str(row.get("file") or "").strip()
        sample_id = raw_id[:-2] if raw_id.endswith("fb") else raw_id
        metadata.append(
            {
                "sample_id": sample_id,
                "condition": str(row.get("condition") or "").strip(),
                "source_accession": dataset["accession"],
                "source_label": raw_id,
            }
        )
    counts = _read_count_rows(
        csv.DictReader(counts_text.splitlines(), delimiter="\t"),
        gene_field="gene_id",
        source_columns={sample: sample for sample in dataset["preprocessing"]["sample_order"]},
    )
    return metadata, counts


def _prepare_gse60450(dataset: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    artifacts = {artifact["name"]: cache_artifact_path(artifact) for artifact in dataset["retrieval"]["artifacts"]}
    with gzip.open(artifacts["GSE60450_series_matrix.txt.gz"], "rt", encoding="utf-8", errors="strict") as source:
        series_text = source.read()
    selection = dataset["preprocessing"]["sample_selection"]
    for item in selection:
        if item["sample_id"] not in series_text or item["source_label"] not in series_text:
            raise ReferenceDataError("GEO sample provenance did not match the pinned series matrix.")
    with gzip.open(artifacts["GSE60450_Lactation-GenewiseCounts.txt.gz"], "rt", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        headers = list(reader.fieldnames or [])
        source_columns: dict[str, str] = {}
        for item in selection:
            matches = [header for header in headers if header.startswith(item["source_prefix"] + "_")]
            if len(matches) != 1:
                raise ReferenceDataError("GEO count column did not uniquely match declared metadata.")
            source_columns[item["sample_id"]] = matches[0]
        counts = _read_count_rows(reader, gene_field="EntrezGeneID", source_columns=source_columns)
    metadata = [
        {
            "sample_id": item["sample_id"],
            "condition": item["condition"],
            "source_accession": item["sample_id"],
            "source_label": item["source_label"],
        }
        for item in selection
    ]
    return metadata, counts


def _tar_text(archive: tarfile.TarFile, member_name: str) -> str:
    try:
        member = archive.getmember(member_name)
        extracted = archive.extractfile(member)
    except (KeyError, tarfile.TarError):
        extracted = None
    if extracted is None or not member.isfile():
        raise ReferenceDataError("Pinned package member is unavailable.")
    return extracted.read().decode("utf-8")


def _read_count_rows(
    rows: Iterable[dict[str, str]], *, gene_field: str, source_columns: dict[str, str]
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row_number, row in enumerate(rows, start=2):
        gene_id = str(row.get(gene_field) or "").strip()
        if not gene_id:
            raise ReferenceDataError(f"Source count row {row_number} has an empty gene identifier.")
        values: dict[str, int] = {}
        for output_sample, source_sample in source_columns.items():
            raw = str(row.get(source_sample) or "").strip()
            try:
                value = int(raw)
            except ValueError as exc:
                raise ReferenceDataError(f"Source count row {row_number} has a non-integer count.") from exc
            if value < 0:
                raise ReferenceDataError(f"Source count row {row_number} has a negative count.")
            values[output_sample] = value
        if gene_id in counts:
            for sample, value in values.items():
                counts[gene_id][sample] += value
        else:
            counts[gene_id] = values
    if not counts:
        raise ReferenceDataError("Source count matrix is empty.")
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_counts(path: Path, counts: dict[str, dict[str, int]], samples: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(["gene_id", *samples])
        for gene_id, values in counts.items():
            writer.writerow([gene_id, *(values[sample] for sample in samples)])


def _verify_prepared_checksums(dataset: dict[str, Any], checksums: dict[str, str]) -> None:
    expected = {entry["role"]: entry["sha256"] for entry in dataset["expected_files"]}
    for role, actual in checksums.items():
        declared = str(expected.get(role) or "")
        if declared == "0" * 64:
            continue
        if actual.lower() != declared.lower():
            raise ReferenceDataError("Prepared input checksum does not match the manifest.")
