import json
from pathlib import Path

import pytest

from backend.app.services.coze_summary import (
    build_coze_task_summary,
    build_download_url,
    sanitize_summary_payload,
)
from backend.app.services.task_registry import create_task, reset_registry, save_task_artifacts


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
        "analysis_method": "deseq2",
        "formal_de_method": "deseq2",
        "status": "deseq2_interpretation_summary_ready",
        "contrast": {
            "contrast_column": "condition",
            "contrast_numerator": "treatment",
            "contrast_denominator": "control",
            "direction": "treatment_vs_control",
            "positive_log2fc_interpretation": "Higher in treatment relative to control",
            "negative_log2fc_interpretation": "Lower in treatment relative to control",
            "contrast_source": "explicit",
            "inferred": False,
        },
        "summary": {
            "padj_threshold": 0.05,
            "abs_log2fc_threshold": 1.0,
            "genes_with_valid_padj": 2,
            "genes_with_na_padj": 1,
            "genes_passing_default_reporting_filter": 1,
            "top_genes_by_padj": [
                {
                    "gene_id": "GeneA",
                    "log2FoldChange": 1.2,
                    "pvalue": 0.001,
                    "padj": 0.002,
                }
            ],
            "top_genes_by_abs_log2fc": [
                {
                    "gene_id": "GeneB",
                    "log2FoldChange": -2.5,
                    "pvalue": 0.01,
                    "padj": 0.04,
                }
            ],
        },
        "threshold_summary": {
            "padj_threshold": 0.05,
            "abs_log2fc_threshold": 1.0,
            "genes_passing_default_reporting_filter": 1,
            "genes_with_valid_padj": 2,
            "genes_with_na_padj": 1,
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


def test_download_url_is_relative_api_path(isolated_task_env: Path) -> None:
    task = create_task()

    download_url = build_download_url(task.task_id, "report.md")

    assert download_url == f"/task/{task.task_id}/artifacts/report.md/download"
    assert not download_url.startswith("file://")
    _assert_no_forbidden_fragments({"download_url": download_url})


def test_minimal_workflow_summary_has_exploratory_boundaries(
    isolated_task_env: Path,
) -> None:
    task = create_task()
    _write_json_artifact(
        isolated_task_env,
        task.task_id,
        "execution_summary.json",
        {
            "contrast": {
                "contrast_column": "condition",
                "contrast_numerator": "treatment",
                "contrast_denominator": "control",
                "direction": "treatment_vs_control",
                "positive_log2fc_interpretation": "Higher in treatment relative to control",
                "negative_log2fc_interpretation": "Lower in treatment relative to control",
                "contrast_source": "explicit",
                "inferred": False,
            }
        },
    )
    _register_artifacts(
        task.task_id,
        [
            {"name": "execution_summary.json", "artifact_type": "minimal_execution_summary"},
            {"name": "normalized_counts_cpm.csv", "artifact_type": "normalized_counts_cpm"},
            {
                "name": "differential_expression_results.csv",
                "artifact_type": "preliminary_log2fc_ranking",
            },
            {"name": "report.md", "artifact_type": "minimal_analysis_report"},
        ],
    )

    summary = build_coze_task_summary(task.task_id)

    assert summary["analysis_method"] == "minimal_cpm_log2fc"
    assert summary["formal_de_method"] is None
    assert summary["statistical_test_performed"] is False
    assert summary["pvalue_available"] is False
    assert summary["adjusted_pvalue_available"] is False
    summary_text = " ".join(summary["warnings"] + summary["limitations"]).lower()
    assert "no p-values" in summary_text
    assert "no adjusted p-values" in summary_text
    assert "no formal" in summary_text
    assert "no batch correction" in summary_text
    assert "no go/kegg/gsea" in summary_text
    assert summary["contrast"]["direction"] == "treatment_vs_control"
    assert summary["positive_log2fc_interpretation"] == (
        "Higher in treatment relative to control"
    )
    _assert_no_forbidden_fragments(summary)


def test_deseq2_summary_reads_interpretation_artifact(
    isolated_task_env: Path,
) -> None:
    task = create_task()
    _write_json_artifact(
        isolated_task_env,
        task.task_id,
        "deseq2_interpretation_summary.json",
        _deseq2_interpretation_payload(),
    )
    _register_artifacts(
        task.task_id,
        [
            {
                "name": "deseq2_interpretation_summary.json",
                "artifact_type": "deseq2_interpretation_summary",
            },
            {"name": "report.md", "artifact_type": "deseq2_analysis_report"},
        ],
    )

    summary = build_coze_task_summary(task.task_id)

    assert summary["analysis_method"] == "deseq2"
    assert summary["formal_de_method"] == "deseq2"
    assert summary["statistical_test_performed"] is True
    assert summary["pvalue_available"] is True
    assert summary["adjusted_pvalue_available"] is True
    assert summary["threshold_summary"]["padj_threshold"] == 0.05
    assert summary["top_genes_by_padj"][0]["gene_id"] == "GeneA"
    assert summary["top_genes_by_abs_log2fc"][0]["gene_id"] == "GeneB"
    assert summary["contrast"]["direction"] == "treatment_vs_control"
    assert summary["negative_log2fc_interpretation"] == (
        "Lower in treatment relative to control"
    )
    _assert_no_forbidden_fragments(summary)


def test_malformed_json_artifact_becomes_safe_partial_summary(
    isolated_task_env: Path,
) -> None:
    task = create_task()
    _write_text_artifact(
        isolated_task_env,
        task.task_id,
        "deseq2_interpretation_summary.json",
        "{not valid json",
    )
    _register_artifacts(
        task.task_id,
        [
            {
                "name": "deseq2_interpretation_summary.json",
                "artifact_type": "deseq2_interpretation_summary",
            }
        ],
    )

    summary = build_coze_task_summary(task.task_id)

    assert summary["analysis_method"] == "deseq2"
    assert "Some result artifacts could not be parsed safely." in summary["warnings"]
    assert summary["safe_to_present"] is True
    _assert_no_forbidden_fragments(summary)


def test_missing_artifacts_become_safe_partial_summary(isolated_task_env: Path) -> None:
    task = create_task()

    summary = build_coze_task_summary(task.task_id)

    assert summary["analysis_method"] is None
    assert summary["summary_message"].startswith("Task exists")
    assert summary["safe_to_present"] is True
    assert summary["warnings"]
    _assert_no_forbidden_fragments(summary)


def test_sanitize_summary_payload_removes_paths_and_secrets() -> None:
    payload = {
        "message": r"D:\private\token.txt /home/user/password file://tmp/secret traceback",
        "nested": [{"path": "/mnt/data/secret.csv"}],
    }

    sanitized = sanitize_summary_payload(payload)

    _assert_no_forbidden_fragments(sanitized)
