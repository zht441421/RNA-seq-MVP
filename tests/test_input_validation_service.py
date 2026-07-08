import os
from pathlib import Path

import pytest

from backend.app.services.input_validation import (
    ALLOWED_RNASEQ_INPUT_SUFFIXES,
    _is_relative_to,
    get_input_root,
    resolve_input_path,
    validate_input_file,
    validate_rnaseq_input_files,
)


def _set_input_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    return input_root


def test_valid_relative_csv_path_under_input_root_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = _set_input_root(monkeypatch, tmp_path)
    demo_dir = input_root / "demo"
    demo_dir.mkdir()
    metadata_path = demo_dir / "metadata.csv"
    metadata_path.write_text("sample_id,condition\ns1,control\n", encoding="utf-8")

    result = validate_input_file(
        "demo/metadata.csv",
        allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES,
    )

    assert get_input_root() == input_root.resolve()
    assert resolve_input_path("demo/metadata.csv") == metadata_path.resolve()
    assert result.valid is True
    assert result.exists is True
    assert result.suffix == ".csv"
    assert result.resolved_path == metadata_path.resolve()
    assert result.errors == []


@pytest.mark.parametrize(
    "path_value",
    [
        r"C:\data\metadata.csv",
        r"D:\data\metadata.csv",
    ],
)
def test_absolute_windows_path_is_rejected(
    path_value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_input_root(monkeypatch, tmp_path)

    result = validate_input_file(path_value, allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES)

    assert result.valid is False
    assert "Absolute paths are not allowed." in result.errors
    assert result.resolved_path is None


def test_absolute_unix_path_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_input_root(monkeypatch, tmp_path)

    result = validate_input_file(
        "/home/user/metadata.csv",
        allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES,
    )

    assert result.valid is False
    assert "Absolute paths are not allowed." in result.errors
    assert result.resolved_path is None


@pytest.mark.parametrize(
    "path_value",
    [
        "../metadata.csv",
        r"demo\..\metadata.csv",
        "demo/../metadata.csv",
    ],
)
def test_path_traversal_is_rejected(
    path_value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_input_root(monkeypatch, tmp_path)

    result = validate_input_file(path_value, allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES)

    assert result.valid is False
    assert "Path traversal is not allowed." in result.errors
    assert result.resolved_path is None


def test_unsupported_suffix_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = _set_input_root(monkeypatch, tmp_path)
    demo_dir = input_root / "demo"
    demo_dir.mkdir()
    xlsx_path = demo_dir / "metadata.xlsx"
    xlsx_path.write_text("not parsed\n", encoding="utf-8")

    result = validate_input_file(
        "demo/metadata.xlsx",
        allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES,
    )

    assert result.valid is False
    assert result.exists is True
    assert result.suffix == ".xlsx"
    assert result.errors == [
        "Unsupported file suffix: .xlsx. Allowed suffixes: .csv, .tsv, .txt."
    ]


@pytest.mark.parametrize("path_value", ["", "   "])
def test_empty_path_is_rejected(
    path_value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_input_root(monkeypatch, tmp_path)

    result = validate_input_file(path_value, allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES)

    assert result.valid is False
    assert result.errors[0] == "Path must be a non-empty relative path."
    assert result.resolved_path is None


def test_null_byte_path_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_input_root(monkeypatch, tmp_path)

    result = validate_input_file(
        "demo/metadata.csv\x00",
        allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES,
    )

    assert result.valid is False
    assert "Path must not contain null bytes." in result.errors
    assert result.resolved_path is None


def test_resolved_path_cannot_escape_input_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = _set_input_root(monkeypatch, tmp_path)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "counts.csv"
    outside_file.write_text("gene_id,s1\nGeneA,1\n", encoding="utf-8")
    link_path = input_root / "linked"

    try:
        link_path.symlink_to(outside_dir, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    result = validate_input_file(
        "linked/counts.csv",
        allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES,
    )

    assert result.valid is False
    assert result.exists is False
    assert result.resolved_path == outside_file.resolve()
    assert result.errors == ["Resolved path escapes input root."]


def test_relative_to_guard_rejects_resolved_path_outside_root(tmp_path: Path) -> None:
    input_root = (tmp_path / "inputs").resolve()
    outside_path = (tmp_path / "outside" / "counts.csv").resolve()

    assert _is_relative_to(outside_path, input_root) is False


def test_rnaseq_input_validation_aggregates_file_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = _set_input_root(monkeypatch, tmp_path)
    demo_dir = input_root / "demo"
    demo_dir.mkdir()
    (demo_dir / "metadata.tsv").write_text("sample_id\tcondition\n", encoding="utf-8")
    (demo_dir / "counts.txt").write_text("gene_id\ts1\nGeneA\t1\n", encoding="utf-8")

    result = validate_rnaseq_input_files(
        metadata_file="demo/metadata.tsv",
        count_matrix_file="demo/counts.txt",
    )

    assert result.valid is True
    assert result.metadata.valid is True
    assert result.count_matrix.valid is True
    assert result.errors == []
    assert result.limitations


def test_resolve_input_path_raises_stable_error_for_unsafe_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_input_root(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="Path traversal is not allowed."):
        resolve_input_path(os.path.join("..", "metadata.csv"))
