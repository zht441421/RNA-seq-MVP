from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

from backend.app.services.artifact_download import (
    ArtifactDownloadError,
    resolve_artifact_download_path,
    validate_download_artifact_name,
)
from backend.app.services.artifact_paths import (
    list_deseq2_artifact_specs,
    list_dry_run_record_specs,
    list_minimal_rnaseq_artifact_specs,
    list_placeholder_artifact_specs,
)
from backend.app.services.task_service import get_task, list_task_artifacts
from backend.app.services.task_inputs import safe_registered_inputs_summary


DESEQ2_INTERPRETATION_ARTIFACT = "deseq2_interpretation_summary.json"
_DESEQ2_RESULT_ARTIFACTS = {
    "deseq2_results.csv",
    DESEQ2_INTERPRETATION_ARTIFACT,
    "deseq2_summary.json",
    "deseq2_run_manifest.json",
}
_MALFORMED_JSON_WARNING = "Some result artifacts could not be parsed safely."
_MISSING_INTERPRETATION_WARNING = (
    "DESeq2 interpretation summary artifact is not available; returning partial summary."
)
_PARTIAL_SUMMARY_LIMITATION = "This is a partial summary based on task metadata and artifact metadata."
_DESEQ2_INTERPRETATION_BOUNDARY = (
    "Statistical significance is not the same as biological significance."
)
_MINIMAL_INTERPRETATION_BOUNDARY = (
    "Exploratory CPM/log2FC ranking is not formal differential expression statistics."
)
_PATH_REPLACEMENTS = (
    re.compile(r"file://[^\s,;)\]}\"']*", re.IGNORECASE),
    re.compile(r"[A-Za-z]:[\\/][^\s,;)\]}\"']*"),
    re.compile(r"/home/[^\s,;)\]}\"']*", re.IGNORECASE),
    re.compile(r"/mnt/[^\s,;)\]}\"']*", re.IGNORECASE),
)
_SENSITIVE_RE = re.compile(r"traceback|token|password|secret", re.IGNORECASE)


class CozeSummaryError(ValueError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def build_coze_task_summary(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise CozeSummaryError(404, "Task not found.")

    artifacts = _known_result_files(task.task_id)
    interpretation, parse_warning = load_safe_json_artifact(
        task.task_id,
        DESEQ2_INTERPRETATION_ARTIFACT,
    )
    warnings = [parse_warning] if parse_warning else []

    if interpretation is not None or _appears_deseq2(artifacts):
        payload = summarize_deseq2_task(
            task_id=task.task_id,
            status=task.status.value,
            result_files=artifacts,
            interpretation=interpretation,
            extra_warnings=warnings,
        )
    elif _appears_minimal(artifacts):
        payload = summarize_minimal_task(
            task_id=task.task_id,
            status=task.status.value,
            result_files=artifacts,
            extra_warnings=warnings,
        )
    else:
        payload = _partial_task_summary(
            task_id=task.task_id,
            status=task.status.value,
            result_files=artifacts,
            extra_warnings=warnings,
        )

    payload["registered_inputs"] = safe_registered_inputs_summary(task.task_id)
    return sanitize_summary_payload(payload)


def _appears_deseq2(artifacts: list[dict]) -> bool:
    artifact_names = {artifact["artifact_name"] for artifact in artifacts}
    artifact_types = {str(artifact.get("artifact_type") or "") for artifact in artifacts}
    return bool(
        artifact_names.intersection(_DESEQ2_RESULT_ARTIFACTS)
        or any(artifact_type.startswith("deseq2") for artifact_type in artifact_types)
    )


def _appears_minimal(artifacts: list[dict]) -> bool:
    artifact_names = {artifact["artifact_name"] for artifact in artifacts}
    artifact_types = {str(artifact.get("artifact_type") or "") for artifact in artifacts}
    return bool(
        "normalized_counts_cpm.csv" in artifact_names
        or any(artifact_type.startswith("minimal") for artifact_type in artifact_types)
    )


def build_download_url(task_id: str, artifact_name: str) -> str:
    safe_name = validate_download_artifact_name(artifact_name)
    return f"/task/{task_id}/artifacts/{quote(safe_name, safe='')}/download"


def summarize_minimal_task(
    *,
    task_id: str,
    status: str,
    result_files: list[dict],
    extra_warnings: list[str] | None = None,
) -> dict:
    warnings = _dedupe(
        [
            *(extra_warnings or []),
            "No p-values are available for the minimal CPM/log2FC workflow.",
            "No adjusted p-values are available for the minimal CPM/log2FC workflow.",
            "No formal statistical test was performed.",
        ]
    )
    limitations = _dedupe(
        [
            "This is an exploratory CPM/log2FC ranking, not formal differential expression statistics.",
            "No p-values are reported.",
            "No adjusted p-values are reported.",
            "No formal statistical model was fitted.",
            "No batch correction was performed.",
            "No GO/KEGG/GSEA enrichment analysis was performed.",
        ]
    )
    return {
        "task_id": task_id,
        "status": status,
        "analysis_method": "minimal_cpm_log2fc",
        "formal_de_method": None,
        "statistical_test_performed": False,
        "pvalue_available": False,
        "adjusted_pvalue_available": False,
        "summary_message": (
            "Minimal CPM/log2FC results are exploratory rankings only and do not "
            "represent formal differential expression statistics."
        ),
        "result_files": result_files,
        "download_links": _download_links(result_files),
        "threshold_summary": {
            "formal_thresholds_available": False,
            "pvalue_threshold": None,
            "adjusted_pvalue_threshold": None,
        },
        "top_genes_by_padj": [],
        "top_genes_by_abs_log2fc": [],
        "warnings": warnings,
        "limitations": limitations,
        "interpretation_boundary": _MINIMAL_INTERPRETATION_BOUNDARY,
        "recommended_next_steps": [
            "Review QC metrics and sample metadata before interpreting rankings.",
            "Run a formal DESeq2, edgeR, or limma workflow before claiming differential expression.",
            "Add batch/covariate modeling in a future phase when metadata supports it.",
        ],
        "safe_to_present": True,
    }


def summarize_deseq2_task(
    *,
    task_id: str,
    status: str,
    result_files: list[dict],
    interpretation: dict | None,
    extra_warnings: list[str] | None = None,
) -> dict:
    summary = _safe_mapping((interpretation or {}).get("summary"))
    threshold_summary = _safe_mapping((interpretation or {}).get("threshold_summary"))
    if not threshold_summary:
        threshold_summary = {
            "padj_threshold": summary.get("padj_threshold"),
            "abs_log2fc_threshold": summary.get("abs_log2fc_threshold"),
            "genes_passing_default_reporting_filter": summary.get(
                "genes_passing_default_reporting_filter"
            ),
            "genes_with_valid_padj": summary.get("genes_with_valid_padj"),
            "genes_with_na_padj": summary.get("genes_with_na_padj"),
        }

    warnings = _dedupe(
        [
            *(extra_warnings or []),
            *((interpretation or {}).get("warnings") or []),
            (
                "log2FoldChange direction depends on DESeq2 contrast/reference level."
            ),
            (
                "NA pvalue or padj may occur because of filtering, low counts, "
                "outlier handling, or model limitations."
            ),
        ]
    )
    limitations = _dedupe(
        [
            *((interpretation or {}).get("limitations") or []),
            "No GO/KEGG/GSEA enrichment analysis was performed.",
            "No batch correction or complex design was performed.",
        ]
    )
    recommended_next_steps = (interpretation or {}).get("recommended_next_steps") or [
        "Review the experimental design and DESeq2 contrast/reference levels.",
        "Inspect genes with NA pvalue or padj before interpreting filtered results.",
        "Use biological context and independent validation before making conclusions.",
    ]

    if interpretation is None:
        warnings = _dedupe([*warnings, _MISSING_INTERPRETATION_WARNING])
        limitations = _dedupe([*limitations, _PARTIAL_SUMMARY_LIMITATION])

    return {
        "task_id": task_id,
        "status": status,
        "analysis_method": "deseq2",
        "formal_de_method": "deseq2",
        "statistical_test_performed": True,
        "pvalue_available": True,
        "adjusted_pvalue_available": True,
        "summary_message": (
            "DESeq2 completed or produced DESeq2 artifact metadata. Candidate genes "
            "are summarized using adjusted p-value and log2 fold-change thresholds; "
            "statistical significance is not the same as biological significance."
        ),
        "result_files": result_files,
        "download_links": _download_links(result_files),
        "threshold_summary": threshold_summary,
        "top_genes_by_padj": _safe_list(summary.get("top_genes_by_padj")),
        "top_genes_by_abs_log2fc": _safe_list(summary.get("top_genes_by_abs_log2fc")),
        "warnings": warnings,
        "limitations": limitations,
        "interpretation_boundary": (interpretation or {}).get(
            "interpretation_boundary",
            _DESEQ2_INTERPRETATION_BOUNDARY,
        ),
        "recommended_next_steps": recommended_next_steps,
        "safe_to_present": True,
    }


def load_safe_json_artifact(task_id: str, artifact_name: str) -> tuple[dict | None, str | None]:
    try:
        artifact_path = resolve_artifact_download_path(task_id, artifact_name)
    except ArtifactDownloadError:
        return None, None

    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None, _MALFORMED_JSON_WARNING

    if not isinstance(payload, dict):
        return None, _MALFORMED_JSON_WARNING

    return payload, None


def sanitize_summary_payload(payload: dict) -> dict:
    return _sanitize_value(payload)


def _partial_task_summary(
    *,
    task_id: str,
    status: str,
    result_files: list[dict],
    extra_warnings: list[str] | None = None,
) -> dict:
    return {
        "task_id": task_id,
        "status": status,
        "analysis_method": None,
        "formal_de_method": None,
        "statistical_test_performed": False,
        "pvalue_available": False,
        "adjusted_pvalue_available": False,
        "summary_message": (
            "Task exists, but completed result summary artifacts are not available yet."
        ),
        "result_files": result_files,
        "download_links": _download_links(result_files),
        "threshold_summary": {},
        "top_genes_by_padj": [],
        "top_genes_by_abs_log2fc": [],
        "warnings": _dedupe(
            [
                *(extra_warnings or []),
                "Result artifacts are incomplete or not available yet.",
            ]
        ),
        "limitations": [
            _PARTIAL_SUMMARY_LIMITATION,
            "No result table contents were read for this summary.",
        ],
        "interpretation_boundary": (
            "No biological or statistical conclusion should be drawn from this partial summary."
        ),
        "recommended_next_steps": [
            "Run or complete the task before presenting result-level findings.",
            "Use the artifacts endpoint to check which task-scoped files are available.",
        ],
        "safe_to_present": True,
    }


def _known_result_files(task_id: str) -> list[dict]:
    persisted_artifacts = list_task_artifacts(task_id)
    if persisted_artifacts:
        artifacts = [
            _artifact_from_persisted_metadata(task_id, artifact)
            for artifact in persisted_artifacts
        ]
    else:
        artifacts = [
            _artifact_from_spec(task_id, artifact)
            for artifact in _planned_artifact_specs(task_id)
        ]

    return [
        artifact
        for artifact in artifacts
        if artifact is not None
    ]


def _artifact_from_persisted_metadata(task_id: str, artifact: dict) -> dict | None:
    artifact_name = str(artifact.get("artifact_name") or "")
    try:
        safe_name = validate_download_artifact_name(artifact_name)
    except ArtifactDownloadError:
        return None
    return _result_file_entry(
        task_id=task_id,
        artifact_name=safe_name,
        artifact_type=str(artifact.get("artifact_type") or "artifact"),
        description=str(artifact.get("description") or "Task artifact."),
        available=_artifact_available(task_id, safe_name),
    )


def _artifact_from_spec(task_id: str, artifact: dict) -> dict | None:
    artifact_name = str(artifact.get("name") or "")
    try:
        safe_name = validate_download_artifact_name(artifact_name)
    except ArtifactDownloadError:
        return None
    return _result_file_entry(
        task_id=task_id,
        artifact_name=safe_name,
        artifact_type=str(artifact.get("artifact_type") or "artifact"),
        description=str(artifact.get("description") or "Task artifact."),
        available=bool(artifact.get("exists")),
    )


def _result_file_entry(
    *,
    task_id: str,
    artifact_name: str,
    artifact_type: str,
    description: str,
    available: bool,
) -> dict:
    return {
        "artifact_name": artifact_name,
        "artifact_type": artifact_type,
        "description": description,
        "download_url": build_download_url(task_id, artifact_name),
        "available": bool(available),
    }


def _planned_artifact_specs(task_id: str) -> list[dict]:
    deseq2_artifacts = list_deseq2_artifact_specs(task_id)
    if any(
        artifact["name"] == "deseq2_results.csv" and artifact["exists"]
        for artifact in deseq2_artifacts
    ):
        return deseq2_artifacts

    minimal_artifacts = list_minimal_rnaseq_artifact_specs(task_id)
    if any(
        artifact["name"] == "normalized_counts_cpm.csv" and artifact["exists"]
        for artifact in minimal_artifacts
    ):
        return minimal_artifacts

    return [
        *list_placeholder_artifact_specs(task_id),
        *[
            artifact
            for artifact in list_dry_run_record_specs(task_id)
            if artifact["exists"]
        ],
    ]


def _artifact_available(task_id: str, artifact_name: str) -> bool:
    try:
        resolve_artifact_download_path(task_id, artifact_name)
    except ArtifactDownloadError:
        return False
    return True


def _download_links(result_files: list[dict]) -> dict:
    return {
        str(result_file["artifact_name"]): str(result_file["download_url"])
        for result_file in result_files
        if result_file.get("artifact_name") and result_file.get("download_url")
    }


def _safe_mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _safe_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _dedupe(values: list[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            _sanitize_key(key): _sanitize_value(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(child) for child in value]
    if isinstance(value, tuple):
        return [_sanitize_value(child) for child in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _sanitize_key(value: object) -> str:
    return _sanitize_text(str(value or ""))


def _sanitize_text(value: str) -> str:
    text = str(value or "")
    for pattern in _PATH_REPLACEMENTS:
        text = pattern.sub("[redacted-path]", text)
    text = _SENSITIVE_RE.sub("redacted", text)
    if _looks_like_absolute_path(text):
        return PurePosixPath(text.replace("\\", "/")).name or "redacted"
    return text


def _looks_like_absolute_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return (
        (len(normalized) > 2 and normalized[1:3] == ":/")
        or normalized.lower().startswith("/home/")
        or normalized.lower().startswith("/mnt/")
        or normalized.lower().startswith("file://")
    )
