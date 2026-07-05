import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.project import Project, ProjectStatus, utc_now
from backend.app.models.qc_report import QCReport
from backend.app.models.reliability import ReliabilityAssessment
from backend.app.utils.file_utils import ensure_project_storage
from backend.app.utils.hashing import sha256_file


class ArtifactStore:
    def __init__(self) -> None:
        self.projects: Dict[str, Project] = {}
        self.files: Dict[str, Dict[str, str]] = {}
        self.inspections: Dict[str, Dict[str, Any]] = {}
        self.analysis_configs: Dict[str, Any] = {}
        self.qc_reports: Dict[str, QCReport] = {}
        self.plans: Dict[str, AnalysisPlan] = {}
        self.reliability: Dict[str, ReliabilityAssessment] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        self.artifacts: Dict[str, List[Dict[str, Any]]] = {}
        self.project_metadata: Dict[str, Dict[str, Any]] = {}

    def create_project(self, name: str, description: Optional[str], omics_type: str) -> Project:
        project_id = f"proj_{uuid4().hex}"
        project = Project(project_id=project_id, name=name, description=description, omics_type=omics_type)
        self.projects[project_id] = project
        return project

    def require_project(self, project_id: str) -> Project:
        project = self.projects.get(project_id)
        if not project:
            raise KeyError(project_id)
        return project

    def update_status(self, project_id: str, status: ProjectStatus) -> Project:
        project = self.require_project(project_id)
        if hasattr(project, "model_copy"):
            project = project.model_copy(update={"status": status, "updated_at": utc_now()})
        else:
            project = project.copy(update={"status": status, "updated_at": utc_now()})
        self.projects[project_id] = project
        return project

    def register_files(self, project_id: str, count_matrix_file: str, metadata_file: str) -> None:
        self.require_project(project_id)
        self.files[project_id] = {
            "count_matrix_file": count_matrix_file,
            "metadata_file": metadata_file,
        }
        self.update_status(project_id, ProjectStatus.FILES_UPLOADED)

    def get_files(self, project_id: str) -> Dict[str, str]:
        self.require_project(project_id)
        if project_id not in self.files:
            raise KeyError(f"No files registered for project {project_id}")
        return self.files[project_id]

    def write_artifact(self, project_id: str, file_name: str, content: str, artifact_type: str) -> Dict[str, Any]:
        artifact_dir = ensure_project_storage(project_id, "artifacts")
        path = artifact_dir / file_name
        path.write_text(content, encoding="utf-8")
        artifact = {
            "name": file_name,
            "type": artifact_type,
            "path": str(path),
            "sha256": sha256_file(path),
        }
        self.artifacts.setdefault(project_id, []).append(artifact)
        return artifact

    def write_json_artifact(self, project_id: str, file_name: str, payload: Dict[str, Any], artifact_type: str) -> Dict[str, Any]:
        return self.write_artifact(
            project_id=project_id,
            file_name=file_name,
            content=json.dumps(payload, indent=2, default=str),
            artifact_type=artifact_type,
        )

    def register_artifact_file(self, project_id: str, path: Path, artifact_type: str) -> Dict[str, Any]:
        self.require_project(project_id)
        artifact = {
            "name": path.name,
            "type": artifact_type,
            "path": str(path),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        self.artifacts.setdefault(project_id, []).append(artifact)
        return artifact

    def list_artifacts(self, project_id: str) -> List[Dict[str, Any]]:
        self.require_project(project_id)
        return self.artifacts.get(project_id, [])


STORE = ArtifactStore()
