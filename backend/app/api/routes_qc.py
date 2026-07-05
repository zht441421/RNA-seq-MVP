from fastapi import APIRouter, HTTPException

from backend.app.models.project import ProjectStatus
from backend.app.models.qc_report import QCReport
from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.services.artifact_service import STORE
from backend.app.services.qc_service import run_qc


router = APIRouter(tags=["qc"])


@router.post("/projects/{project_id}/qc", response_model=QCReport)
def run_project_qc(project_id: str, config: BulkRNASeqAnalysisConfig) -> QCReport:
    _require_matching_project(project_id, config.project_id)
    report = run_qc(config)
    STORE.analysis_configs[project_id] = config
    STORE.qc_reports[project_id] = report
    STORE.update_status(project_id, ProjectStatus.QC_COMPLETED)
    return report


def _require_matching_project(path_project_id: str, body_project_id: str) -> None:
    try:
        STORE.require_project(path_project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {path_project_id}") from exc
    if path_project_id != body_project_id:
        raise HTTPException(status_code=400, detail="Path project_id does not match request project_id.")

