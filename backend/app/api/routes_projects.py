from fastapi import APIRouter

from backend.app.models.schemas import ProjectCreateRequest, ProjectResponse
from backend.app.services.artifact_service import STORE


router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectResponse)
def create_project(request: ProjectCreateRequest) -> ProjectResponse:
    project = STORE.create_project(
        name=request.name,
        description=request.description,
        omics_type=request.omics_type.value,
    )
    return ProjectResponse(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        omics_type=project.omics_type,
        status=project.status,
    )

