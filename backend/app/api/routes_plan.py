from fastapi import APIRouter, HTTPException

from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.project import ProjectStatus
from backend.app.models.schemas import BulkRNASeqAnalysisConfig, ConfirmPlanRequest
from backend.app.services.artifact_service import STORE
from backend.app.services.plan_service import create_recommended_plan


router = APIRouter(tags=["plan"])


@router.post("/projects/{project_id}/plan", response_model=AnalysisPlan)
def create_plan(project_id: str, config: BulkRNASeqAnalysisConfig) -> AnalysisPlan:
    _require_matching_project(project_id, config.project_id)
    qc_report = STORE.qc_reports.get(project_id)
    plan = create_recommended_plan(config=config, qc_report=qc_report)
    STORE.analysis_configs[project_id] = config
    STORE.plans[project_id] = plan
    STORE.update_status(project_id, ProjectStatus.PLAN_PROPOSED)
    return plan


@router.post("/projects/{project_id}/confirm-plan", response_model=AnalysisPlan)
def confirm_plan(project_id: str, request: ConfirmPlanRequest) -> AnalysisPlan:
    _require_project(project_id)
    plan = STORE.plans.get(project_id)
    if not plan:
        raise HTTPException(status_code=400, detail="No analysis plan has been proposed for this project.")
    if plan.plan_id != request.plan_id:
        raise HTTPException(status_code=400, detail="Plan ID does not match the active plan.")
    if hasattr(plan, "model_copy"):
        plan = plan.model_copy(update={"confirmed": request.confirmed})
    else:
        plan = plan.copy(update={"confirmed": request.confirmed})
    STORE.plans[project_id] = plan
    if request.confirmed:
        STORE.update_status(project_id, ProjectStatus.PLAN_CONFIRMED)
    return plan


def _require_matching_project(path_project_id: str, body_project_id: str) -> None:
    _require_project(path_project_id)
    if path_project_id != body_project_id:
        raise HTTPException(status_code=400, detail="Path project_id does not match request project_id.")


def _require_project(project_id: str) -> None:
    try:
        STORE.require_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
