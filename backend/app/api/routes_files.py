from typing import Optional

from fastapi import APIRouter, Body, HTTPException

from backend.app.models.project import ProjectStatus
from backend.app.models.schemas import (
    FileRegistrationRequest,
    FileRegistrationResponse,
    InspectRequest,
    InspectResponse,
)
from backend.app.services.artifact_service import STORE
from backend.app.services.file_inspector import inspect_file
from backend.app.services.schema_detector import detect_schema


router = APIRouter(tags=["files"])


@router.post("/projects/{project_id}/files", response_model=FileRegistrationResponse)
def register_files(project_id: str, request: FileRegistrationRequest) -> FileRegistrationResponse:
    _require_project(project_id)
    try:
        inspect_file(request.count_matrix_file)
        inspect_file(request.metadata_file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    STORE.register_files(
        project_id=project_id,
        count_matrix_file=request.count_matrix_file,
        metadata_file=request.metadata_file,
    )
    project = STORE.require_project(project_id)
    return FileRegistrationResponse(
        project_id=project_id,
        count_matrix_file=request.count_matrix_file,
        metadata_file=request.metadata_file,
        status=project.status,
    )


@router.post("/projects/{project_id}/inspect", response_model=InspectResponse)
def inspect_project(
    project_id: str,
    request: Optional[InspectRequest] = Body(default=None),
) -> InspectResponse:
    _require_project(project_id)
    files = _resolve_files(project_id, request)
    try:
        count_matrix = inspect_file(files["count_matrix_file"])
        metadata = inspect_file(files["metadata_file"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    detected_schema = detect_schema(count_matrix=count_matrix, metadata=metadata)
    response = InspectResponse(
        project_id=project_id,
        count_matrix=count_matrix,
        metadata=metadata,
        detected_schema=detected_schema,
    )
    if hasattr(response, "model_dump"):
        STORE.inspections[project_id] = response.model_dump()
    else:
        STORE.inspections[project_id] = response.dict()
    STORE.update_status(project_id, ProjectStatus.INSPECTED)
    return response


def _resolve_files(project_id: str, request: Optional[InspectRequest]) -> dict[str, str]:
    if request and request.count_matrix_file and request.metadata_file:
        return {
            "count_matrix_file": request.count_matrix_file,
            "metadata_file": request.metadata_file,
        }
    try:
        return STORE.get_files(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _require_project(project_id: str) -> None:
    try:
        STORE.require_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
