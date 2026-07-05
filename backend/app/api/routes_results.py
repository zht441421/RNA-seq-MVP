import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.app.config import get_settings
from backend.app.models.schemas import ResultsResponse, StatusResponse
from backend.app.services.artifact_service import STORE
from backend.app.services.export_package import (
    ExportPackageError,
    create_export_package,
    get_export_package_metadata,
)
from backend.app.services.report_summary import build_report_review_summary
from backend.app.services.result_interpretation import build_result_interpretation


router = APIRouter(tags=["results"])


@router.get("/projects/{project_id}/status", response_model=StatusResponse)
def get_project_status(project_id: str) -> StatusResponse:
    project = _require_project(project_id)
    details = {
        "files_registered": project_id in STORE.files,
        "inspected": project_id in STORE.inspections,
        "qc_completed": project_id in STORE.qc_reports,
        "plan_available": project_id in STORE.plans,
        "reliability_available": project_id in STORE.reliability,
        "artifact_count": len(STORE.artifacts.get(project_id, [])),
    }
    return StatusResponse(project_id=project_id, status=project.status, details=details)


@router.get("/projects/{project_id}/results", response_model=ResultsResponse)
def get_project_results(project_id: str) -> ResultsResponse:
    project = _require_project(project_id)
    result_summary = STORE.results.get(project_id, {})
    reliability = STORE.reliability.get(project_id)
    review = build_report_review_summary(
        project_id=project_id,
        status=project.status,
        reliability=reliability,
        result_summary=result_summary,
    )
    interpretation = build_result_interpretation(
        project_id=project_id,
        reliability=reliability,
        result_summary={"status": project.status.value, **result_summary},
    )
    return ResultsResponse(
        project_id=project_id,
        status=project.status,
        reliability=reliability,
        result_summary=result_summary,
        **review,
        interpretation_summary=interpretation,
        top_genes=interpretation.get("top_genes", []),
        interpretation_guardrails=interpretation.get("guardrails", []),
    )


@router.get("/projects/{project_id}/artifacts")
def get_project_artifacts(project_id: str) -> dict:
    _require_project(project_id)
    manifest_path = get_settings().project_root / "artifacts" / project_id / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "project_id": project_id,
        "evidence_package_generated": False,
        "message": "Evidence package not generated; returning current artifact list.",
        "artifacts": STORE.list_artifacts(project_id),
    }


@router.post("/projects/{project_id}/export")
def create_project_export(project_id: str) -> dict:
    _require_project(project_id)
    try:
        return create_export_package(project_id)
    except ExportPackageError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc


@router.get("/projects/{project_id}/export")
def get_project_export(project_id: str) -> dict:
    _require_project(project_id)
    return get_export_package_metadata(project_id)


def _require_project(project_id: str):
    try:
        return STORE.require_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
