import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_registry import reset_registry, save_task_artifacts


FORBIDDEN_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "traceback",
    "token",
    "password",
    "secret",
)


@pytest.fixture()
def isolated_task_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("BIOINFO_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("BIOINFO_TASK_STORE_PATH", str(tmp_path / "state" / "tasks.sqlite3"))
    reset_registry()
    yield output_root
    reset_registry()


def _assert_no_forbidden_fragments(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_FRAGMENTS)


def _create_task(client: TestClient) -> str:
    response = client.post("/task/create", json={})
    assert response.status_code == 200
    return response.json()["task_id"]


def _register_artifacts(task_id: str, artifacts: list[dict]) -> None:
    save_task_artifacts(
        task_id,
        [
            {
                "name": artifact["name"],
                "artifact_type": artifact.get("artifact_type", "artifact"),
                "path": f"tasks/{task_id}/{artifact['name']}",
                "description": artifact.get("description", "Task artifact."),
                "available": artifact.get("available", True),
            }
            for artifact in artifacts
        ],
    )


def _write_text_artifact(
    output_root: Path,
    task_id: str,
    artifact_name: str,
    text: str,
) -> None:
    artifact_path = output_root / "tasks" / task_id / artifact_name
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(text, encoding="utf-8")


def _write_json_artifact(
    output_root: Path,
    task_id: str,
    artifact_name: str,
    payload: dict,
) -> None:
    _write_text_artifact(
        output_root,
        task_id,
        artifact_name,
        json.dumps(payload, sort_keys=True),
    )


def _deseq2_interpretation_payload() -> dict:
    return {
        "summary": {
            "padj_threshold": 0.05,
            "abs_log2fc_threshold": 1.0,
            "genes_with_valid_padj": 2,
            "genes_with_na_padj": 0,
            "genes_passing_default_reporting_filter": 1,
            "top_genes_by_padj": [
                {"gene_id": "GeneA", "log2FoldChange": 1.4, "pvalue": 0.001, "padj": 0.002}
            ],
            "top_genes_by_abs_log2fc": [
                {"gene_id": "GeneB", "log2FoldChange": -2.0, "pvalue": 0.02, "padj": 0.04}
            ],
        },
        "threshold_summary": {
            "padj_threshold": 0.05,
            "abs_log2fc_threshold": 1.0,
            "genes_passing_default_reporting_filter": 1,
            "genes_with_valid_padj": 2,
            "genes_with_na_padj": 0,
        },
        "warnings": [
            "log2FoldChange direction depends on DESeq2 contrast/reference level."
        ],
        "limitations": [
            "No GO/KEGG/GSEA enrichment analysis was performed.",
            "No batch correction or complex design was performed.",
        ],
        "interpretation_boundary": (
            "Statistical significance is not the same as biological significance."
        ),
        "recommended_next_steps": [
            "Review the experimental design and DESeq2 contrast/reference levels."
        ],
    }


def test_unknown_task_coze_summary_returns_deterministic_404(
    isolated_task_env: Path,
) -> None:
    response = TestClient(app).get("/task/task_missing/coze-summary")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found."}
    _assert_no_forbidden_fragments(response.json())


def test_created_task_with_minimal_artifacts_returns_safe_summary(
    isolated_task_env: Path,
) -> None:
    client = TestClient(app)
    task_id = _create_task(client)
    _register_artifacts(
        task_id,
        [
            {"name": "normalized_counts_cpm.csv", "artifact_type": "normalized_counts_cpm"},
            {
                "name": "differential_expression_results.csv",
                "artifact_type": "preliminary_log2fc_ranking",
            },
            {"name": "report.md", "artifact_type": "minimal_analysis_report"},
        ],
    )

    response = client.get(f"/task/{task_id}/coze-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_method"] == "minimal_cpm_log2fc"
    assert body["formal_de_method"] is None
    assert body["statistical_test_performed"] is False
    assert body["pvalue_available"] is False
    assert body["adjusted_pvalue_available"] is False
    assert body["download_links"]["report.md"] == (
        f"/task/{task_id}/artifacts/report.md/download"
    )
    _assert_no_forbidden_fragments(body)


def test_mocked_deseq2_task_with_interpretation_artifact_returns_summary(
    isolated_task_env: Path,
) -> None:
    client = TestClient(app)
    task_id = _create_task(client)
    _write_json_artifact(
        isolated_task_env,
        task_id,
        "deseq2_interpretation_summary.json",
        _deseq2_interpretation_payload(),
    )
    _write_text_artifact(isolated_task_env, task_id, "report.md", "# Report\n")
    _register_artifacts(
        task_id,
        [
            {
                "name": "deseq2_interpretation_summary.json",
                "artifact_type": "deseq2_interpretation_summary",
            },
            {"name": "report.md", "artifact_type": "deseq2_analysis_report"},
        ],
    )

    response = client.get(f"/task/{task_id}/coze-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_method"] == "deseq2"
    assert body["formal_de_method"] == "deseq2"
    assert body["threshold_summary"]["padj_threshold"] == 0.05
    assert body["top_genes_by_padj"][0]["gene_id"] == "GeneA"
    assert body["top_genes_by_abs_log2fc"][0]["gene_id"] == "GeneB"
    assert body["download_links"]["report.md"] == (
        f"/task/{task_id}/artifacts/report.md/download"
    )
    assert body["download_links"]["deseq2_interpretation_summary.json"] == (
        f"/task/{task_id}/artifacts/deseq2_interpretation_summary.json/download"
    )
    _assert_no_forbidden_fragments(body)


def test_incomplete_task_returns_safe_partial_summary(
    isolated_task_env: Path,
) -> None:
    client = TestClient(app)
    task_id = _create_task(client)

    response = client.get(f"/task/{task_id}/coze-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_method"] is None
    assert body["safe_to_present"] is True
    assert body["warnings"]
    assert body["top_genes_by_padj"] == []
    _assert_no_forbidden_fragments(body)
