import json
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.config import get_settings
from backend.app.models.project import ProjectStatus
from backend.app.models.reliability import ReliabilityAssessment


KEY_ARTIFACTS = [
    "04_main_results/deseq2_results.csv",
    "05_validation_results/edger_results.csv",
    "05_validation_results/limma_voom_results.csv",
    "05_validation_results/validation_comparison.csv",
    "09_environment/run_status.json",
    "09_environment/r_session_info.txt",
    "10_audit_log.json",
    "11_reliability_report.md",
    "12_interpretation_summary.md",
    "manifest.json",
    "08_reproducible_code/README_REPRODUCE.md",
    "08_reproducible_code/analysis_config.json",
    "08_reproducible_code/run_command.txt",
    "08_reproducible_code/docker_command.txt",
    "08_reproducible_code/input_hashes.json",
    "08_reproducible_code/software_versions.json",
]


def build_report_review_summary(
    project_id: str,
    status: Optional[ProjectStatus | str] = None,
    reliability: Optional[ReliabilityAssessment] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    manifest: Optional[Dict[str, Any]] = None,
    audit_log: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result_summary = result_summary or {}
    audit_log = audit_log or {}
    manifest = manifest or load_manifest(project_id) or {}
    run_status = run_status_for_project(project_id, result_summary=result_summary, audit_log=audit_log)

    grade = reliability.grade.value if reliability else audit_log.get("reliability", {}).get("grade")
    strong_allowed = bool(reliability.strong_conclusion_allowed) if reliability else grade in {"A", "B"}
    if grade in {"C", "D", "E", None} or run_status.get("primary_method_status") == "completed_with_warning":
        strong_allowed = False

    return {
        "final_status": _status_value(status),
        "reliability_grade": grade,
        "strong_conclusion_allowed": strong_allowed,
        "primary_method_status": run_status.get("primary_method_status"),
        "warnings": run_status.get("warnings") or [],
        "errors": run_status.get("errors") or [],
        "validation_consistency_score": run_status.get("validation_consistency_score"),
        "artifact_presence_summary": artifact_presence_summary(manifest),
    }


def artifact_presence_summary(manifest: Optional[Dict[str, Any]]) -> Dict[str, str]:
    status_by_path = {
        entry.get("relative_path"): entry.get("status")
        for entry in (manifest or {}).get("files", [])
        if entry.get("relative_path")
    }
    return {relative_path: status_by_path.get(relative_path, "missing") for relative_path in KEY_ARTIFACTS}


def load_manifest(project_id: str) -> Optional[Dict[str, Any]]:
    path = artifact_root(project_id) / "manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run_status_for_project(
    project_id: str,
    result_summary: Optional[Dict[str, Any]] = None,
    audit_log: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result_summary = result_summary or {}
    audit_log = audit_log or {}
    result_run_status = result_summary.get("run_status")
    if isinstance(result_run_status, dict):
        return result_run_status
    audit_run_status = audit_log.get("run_status")
    if isinstance(audit_run_status, dict):
        return audit_run_status
    path = artifact_root(project_id) / "09_environment" / "run_status.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def artifact_root(project_id: str) -> Path:
    return get_settings().project_root / "artifacts" / project_id


def _status_value(status: Optional[ProjectStatus | str]) -> Optional[str]:
    if status is None:
        return None
    value = getattr(status, "value", status)
    return str(value)
