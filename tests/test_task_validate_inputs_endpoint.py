import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


FORBIDDEN_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "secret",
    "token",
    "password",
)


def _assert_no_forbidden_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


def _set_input_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    monkeypatch.setenv("BIOINFO_INPUT_ROOT", str(input_root))
    return input_root


def test_validate_inputs_endpoint_returns_sanitized_valid_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = _set_input_root(monkeypatch, tmp_path)
    demo_dir = input_root / "demo"
    demo_dir.mkdir()
    (demo_dir / "metadata.csv").write_text("sample_id,condition\ns1,control\n", encoding="utf-8")
    (demo_dir / "counts.csv").write_text("gene_id,s1\nGeneA,1\n", encoding="utf-8")

    response = TestClient(app).post(
        "/task/validate-inputs",
        json={
            "metadata_file": "demo/metadata.csv",
            "count_matrix_file": "demo/counts.csv",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "input_validation_completed"
    assert body["valid"] is True
    assert body["metadata"]["safe_relative_path"] == "demo/metadata.csv"
    assert body["metadata"]["exists"] is True
    assert body["metadata"]["suffix"] == ".csv"
    assert body["metadata"]["valid"] is True
    assert body["metadata"]["errors"] == []
    assert body["count_matrix"]["safe_relative_path"] == "demo/counts.csv"
    assert body["count_matrix"]["exists"] is True
    assert body["count_matrix"]["valid"] is True
    assert body["errors"] == []
    assert body["limitations"]
    _assert_no_forbidden_fragments(body)


def test_validate_inputs_endpoint_rejects_unsafe_paths_without_leaking_them(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_input_root(monkeypatch, tmp_path)

    response = TestClient(app).post(
        "/task/validate-inputs",
        json={
            "metadata_file": r"C:\secret\metadata.csv",
            "count_matrix_file": "../counts.csv",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "input_validation_completed"
    assert body["valid"] is False
    assert body["metadata"]["safe_relative_path"] is None
    assert body["metadata"]["valid"] is False
    assert "Absolute paths are not allowed." in body["metadata"]["errors"]
    assert body["count_matrix"]["safe_relative_path"] is None
    assert body["count_matrix"]["valid"] is False
    assert "Path traversal is not allowed." in body["count_matrix"]["errors"]
    assert "metadata_file: Absolute paths are not allowed." in body["errors"]
    assert "count_matrix_file: Path traversal is not allowed." in body["errors"]
    _assert_no_forbidden_fragments(body)
