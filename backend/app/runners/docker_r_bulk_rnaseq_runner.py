import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.config import get_settings
from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.runners.r_bulk_rnaseq_runner import (
    discover_real_run_artifacts,
    is_primary_method_success,
    parse_run_status,
)
from backend.app.utils.file_utils import resolve_input_path


class DockerRBulkRNASeqRunner:
    def __init__(
        self,
        docker_executable: Optional[str] = None,
        image_name: Optional[str] = None,
        docker_workdir: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.project_root = settings.project_root
        self.docker_executable = docker_executable or settings.docker_executable
        self.image_name = image_name or settings.docker_r_image
        self.docker_workdir = docker_workdir or settings.docker_workdir

    def default_output_dir(self, project_id: str) -> Path:
        return self.project_root / "artifacts" / project_id

    def build_analysis_config(
        self,
        config: BulkRNASeqAnalysisConfig,
        plan: AnalysisPlan,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        host_output_dir = output_dir or self.default_output_dir(config.project_id)
        return {
            "project_id": config.project_id,
            "count_matrix_path": self._container_path(resolve_input_path(config.count_matrix_file)),
            "metadata_path": self._container_path(resolve_input_path(config.metadata_file)),
            "gene_id_column": config.gene_id_column,
            "sample_id_column": config.sample_id_column,
            "group_column": config.group_column,
            "reference_group": config.reference_group,
            "test_group": config.test_group,
            "batch_column": config.batch_column,
            "covariates": config.covariates,
            "fdr_threshold": plan.fdr_threshold,
            "log2fc_threshold": plan.log2fc_threshold,
            "output_dir": self._container_path(host_output_dir),
        }

    def write_analysis_config(self, analysis_config: Dict[str, Any], output_dir: Path) -> Path:
        env_dir = output_dir / "09_environment"
        env_dir.mkdir(parents=True, exist_ok=True)
        config_path = env_dir / "analysis_config.json"
        config_path.write_text(json.dumps(analysis_config, indent=2), encoding="utf-8")
        return config_path

    def build_docker_command(self, analysis_config_path: Path) -> List[str]:
        return [
            self.docker_executable,
            "run",
            "--rm",
            "-v",
            f"{self.project_root}:{self.docker_workdir}",
            "-w",
            self.docker_workdir,
            self.image_name,
            "Rscript",
            "backend/app/scripts/r/bulk_rnaseq_de.R",
            self._container_path(analysis_config_path),
        ]

    def run(self, config: BulkRNASeqAnalysisConfig, plan: AnalysisPlan) -> Dict[str, Any]:
        output_dir = self.default_output_dir(config.project_id)
        analysis_config = self.build_analysis_config(config=config, plan=plan, output_dir=output_dir)
        config_path = self.write_analysis_config(analysis_config=analysis_config, output_dir=output_dir)
        env_dir = output_dir / "09_environment"
        stdout_path = env_dir / "docker_r_stdout.log"
        stderr_path = env_dir / "docker_r_stderr.log"
        run_status_path = env_dir / "run_status.json"

        image_check = self._check_image()
        if not image_check["ok"]:
            run_status = self._write_failure_status(
                run_status_path=run_status_path,
                project_id=config.project_id,
                consistency_status=image_check["status"],
                error=image_check["error"],
            )
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(image_check.get("stderr", ""), encoding="utf-8")
            return self._result(config, output_dir, config_path, stdout_path, stderr_path, run_status_path, None, run_status)

        command = self.build_docker_command(config_path)
        returncode: Optional[int]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            returncode = completed.returncode
            stdout_path.write_text(completed.stdout or "", encoding="utf-8")
            stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        except FileNotFoundError as exc:
            returncode = None
            run_status = self._write_failure_status(
                run_status_path=run_status_path,
                project_id=config.project_id,
                consistency_status="docker_unavailable",
                error=f"Docker executable was not found: {self.docker_executable}",
            )
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(str(exc), encoding="utf-8")
            return self._result(config, output_dir, config_path, stdout_path, stderr_path, run_status_path, returncode, run_status)

        run_status = parse_run_status(run_status_path)
        if returncode != 0 and run_status.get("primary_method_status") == "failed" and not run_status.get("errors"):
            run_status["errors"] = ["Docker R runner failed. See docker_r_stderr.log."]
            run_status_path.write_text(json.dumps(run_status, indent=2), encoding="utf-8")

        return self._result(config, output_dir, config_path, stdout_path, stderr_path, run_status_path, returncode, run_status)

    def _result(
        self,
        config: BulkRNASeqAnalysisConfig,
        output_dir: Path,
        config_path: Path,
        stdout_path: Path,
        stderr_path: Path,
        run_status_path: Path,
        returncode: Optional[int],
        run_status: Dict[str, Any],
    ) -> Dict[str, Any]:
        audit_log_path = output_dir / "09_environment" / "docker_r_audit_log.json"
        audit_payload = {
            "execution_mode": "docker_r",
            "docker_image": self.image_name,
            "docker_executable": self.docker_executable,
            "docker_available": returncode is not None or run_status.get("validation_consistency_status") != "docker_unavailable",
            "returncode": returncode,
            "analysis_config_path": str(config_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "run_status_path": str(run_status_path),
        }
        audit_log_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
        run_status["audit_log_path"] = str(audit_log_path)
        run_status["docker_image"] = self.image_name
        run_status["docker_available"] = audit_payload["docker_available"]
        if run_status_path.exists():
            run_status_path.write_text(json.dumps(run_status, indent=2), encoding="utf-8")

        return {
            "mode": "docker_r",
            "project_id": config.project_id,
            "status": "completed" if returncode == 0 and is_primary_method_success(run_status) else "failed",
            "returncode": returncode,
            "analysis_config": json.loads(config_path.read_text(encoding="utf-8")),
            "analysis_config_path": str(config_path),
            "output_dir": str(output_dir),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "audit_log_path": str(audit_log_path),
            "run_status_path": str(run_status_path),
            "run_status": run_status,
            "validation_status": _validation_status_from_run_status(run_status),
            "docker_image": self.image_name,
            "docker_available": audit_payload["docker_available"],
            "artifacts": discover_real_run_artifacts(output_dir),
        }

    def _check_image(self) -> Dict[str, Any]:
        try:
            docker_check = subprocess.run(
                [self.docker_executable, "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if docker_check.returncode != 0:
                return {
                    "ok": False,
                    "status": "docker_unavailable",
                    "error": "Docker is not available.",
                    "stderr": docker_check.stderr,
                }
            completed = subprocess.run(
                [self.docker_executable, "image", "inspect", self.image_name],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            return {
                "ok": False,
                "status": "docker_unavailable",
                "error": f"Docker executable was not found: {self.docker_executable}",
                "stderr": str(exc),
            }
        if completed.returncode != 0:
            return {
                "ok": False,
                "status": "docker_image_unavailable",
                "error": f"Docker image is not available: {self.image_name}",
                "stderr": completed.stderr,
            }
        return {"ok": True}

    def _write_failure_status(
        self,
        run_status_path: Path,
        project_id: str,
        consistency_status: str,
        error: str,
    ) -> Dict[str, Any]:
        run_status_path.parent.mkdir(parents=True, exist_ok=True)
        run_status = {
            "project_id": project_id,
            "execution_mode": "docker_r",
            "primary_method_status": "failed",
            "validation_method_status": {},
            "validation_consistency_score": None,
            "validation_consistency_status": consistency_status,
            "fdr_applied": False,
            "errors": [error],
            "warnings": [],
            "run_status_path": str(run_status_path),
            "docker_image": self.image_name,
        }
        run_status_path.write_text(json.dumps(run_status, indent=2), encoding="utf-8")
        return run_status

    def _container_path(self, host_path: Path) -> str:
        resolved = host_path.resolve()
        relative = resolved.relative_to(self.project_root.resolve())
        return str(Path(self.docker_workdir) / relative).replace("\\", "/")


def _validation_status_from_run_status(run_status: Dict[str, Any]) -> Dict[str, Any]:
    method_statuses = run_status.get("validation_method_status") or {}
    completed_methods = [method for method, status in method_statuses.items() if status == "completed"]
    skipped_methods = [method for method, status in method_statuses.items() if status == "skipped"]
    failed_methods = [method for method, status in method_statuses.items() if status == "failed"]
    return {
        "mode": "docker_r",
        "completed_methods": completed_methods,
        "skipped_methods": skipped_methods,
        "failed_methods": failed_methods,
        "validation_consistency_score": run_status.get("validation_consistency_score"),
        "validation_consistency_status": run_status.get("validation_consistency_status"),
    }
