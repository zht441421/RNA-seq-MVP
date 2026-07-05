import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.config import get_settings
from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.utils.file_utils import resolve_input_path


PRIMARY_METHOD_SUCCESS_STATUSES = {"completed", "completed_with_warning"}


class RBulkRNASeqRunner:
    def __init__(self, rscript_executable: Optional[str] = None) -> None:
        settings = get_settings()
        self.rscript_executable = rscript_executable or settings.rscript_executable
        self.script_path = settings.project_root / "backend" / "app" / "scripts" / "r" / "bulk_rnaseq_de.R"

    def build_analysis_config(
        self,
        config: BulkRNASeqAnalysisConfig,
        plan: AnalysisPlan,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        output_path = output_dir or self.default_output_dir(config.project_id)
        return {
            "project_id": config.project_id,
            "count_matrix_path": str(resolve_input_path(config.count_matrix_file)),
            "metadata_path": str(resolve_input_path(config.metadata_file)),
            "gene_id_column": config.gene_id_column,
            "sample_id_column": config.sample_id_column,
            "group_column": config.group_column,
            "reference_group": config.reference_group,
            "test_group": config.test_group,
            "batch_column": config.batch_column,
            "covariates": config.covariates,
            "fdr_threshold": plan.fdr_threshold,
            "log2fc_threshold": plan.log2fc_threshold,
            "output_dir": str(output_path),
        }

    def default_output_dir(self, project_id: str) -> Path:
        return get_settings().project_root / "artifacts" / project_id

    def write_analysis_config(self, analysis_config: Dict[str, Any], output_dir: Path) -> Path:
        env_dir = output_dir / "09_environment"
        env_dir.mkdir(parents=True, exist_ok=True)
        config_path = env_dir / "analysis_config.json"
        config_path.write_text(json.dumps(analysis_config, indent=2), encoding="utf-8")
        return config_path

    def run(self, config: BulkRNASeqAnalysisConfig, plan: AnalysisPlan) -> Dict[str, Any]:
        output_dir = self.default_output_dir(config.project_id)
        analysis_config = self.build_analysis_config(config=config, plan=plan, output_dir=output_dir)
        config_path = self.write_analysis_config(analysis_config=analysis_config, output_dir=output_dir)
        env_dir = output_dir / "09_environment"
        stdout_path = env_dir / "r_stdout.log"
        stderr_path = env_dir / "r_stderr.log"

        command = [self.rscript_executable, str(self.script_path), str(config_path)]
        returncode: Optional[int]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            returncode = completed.returncode
            stdout_path.write_text(completed.stdout or "", encoding="utf-8")
            stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        except FileNotFoundError as exc:
            returncode = None
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(str(exc), encoding="utf-8")

        run_status_path = env_dir / "run_status.json"
        run_status = parse_run_status(run_status_path)
        if returncode is None:
            run_status.update(
                {
                    "execution_mode": "real_r",
                    "primary_method_status": "failed",
                    "validation_method_status": {},
                    "validation_consistency_score": None,
                    "validation_consistency_status": "rscript_unavailable",
                    "fdr_applied": False,
                    "errors": [f"Rscript executable was not found: {self.rscript_executable}"],
                    "warnings": [],
                    "run_status_path": str(run_status_path),
                }
            )
            run_status_path.write_text(json.dumps(run_status, indent=2), encoding="utf-8")
        audit_log_path = env_dir / "audit_log.json"
        audit_payload = {
            "execution_mode": "real_r",
            "command": command,
            "returncode": returncode,
            "analysis_config_path": str(config_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "run_status_path": str(run_status_path),
        }
        audit_log_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
        run_status["audit_log_path"] = str(audit_log_path)
        if run_status_path.exists():
            run_status_path.write_text(json.dumps(run_status, indent=2), encoding="utf-8")

        return {
            "mode": "real_r",
            "project_id": config.project_id,
            "status": "completed" if returncode == 0 and is_primary_method_success(run_status) else "failed",
            "returncode": returncode,
            "analysis_config": analysis_config,
            "analysis_config_path": str(config_path),
            "output_dir": str(output_dir),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "audit_log_path": str(audit_log_path),
            "run_status_path": str(run_status_path),
            "run_status": run_status,
            "validation_status": _validation_status_from_run_status(run_status),
            "artifacts": discover_real_run_artifacts(output_dir),
        }


def parse_run_status(run_status_path: Path) -> Dict[str, Any]:
    if not run_status_path.exists():
        return {
            "execution_mode": "real_r",
            "primary_method_status": "failed",
            "validation_method_status": {},
            "validation_consistency_score": None,
            "validation_consistency_status": "missing_run_status",
            "fdr_applied": False,
            "errors": [f"run_status.json is missing: {run_status_path}"],
            "warnings": [],
            "r_session_info_path": None,
            "run_status_path": str(run_status_path),
        }
    try:
        return json.loads(run_status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "execution_mode": "real_r",
            "primary_method_status": "failed",
            "validation_method_status": {},
            "validation_consistency_score": None,
            "validation_consistency_status": "invalid_run_status",
            "fdr_applied": False,
            "errors": [f"run_status.json is invalid: {exc}"],
            "warnings": [],
            "r_session_info_path": None,
            "run_status_path": str(run_status_path),
        }


def is_primary_method_success(run_status: Dict[str, Any]) -> bool:
    return run_status.get("primary_method_status") in PRIMARY_METHOD_SUCCESS_STATUSES


def discover_real_run_artifacts(output_dir: Path) -> List[Dict[str, Any]]:
    artifact_types = {
        "04_main_results": "main_result",
        "05_validation_results": "validation_result",
        "06_figures": "figure",
        "07_tables": "table",
        "09_environment": "environment",
    }
    artifacts: List[Dict[str, Any]] = []
    if not output_dir.exists():
        return artifacts
    for child in output_dir.rglob("*"):
        if not child.is_file():
            continue
        relative_parts = child.relative_to(output_dir).parts
        artifact_type = artifact_types.get(relative_parts[0], "real_run_artifact") if relative_parts else "real_run_artifact"
        artifacts.append(
            {
                "name": child.name,
                "type": artifact_type,
                "path": str(child),
            }
        )
    return sorted(artifacts, key=lambda item: item["path"])


def _validation_status_from_run_status(run_status: Dict[str, Any]) -> Dict[str, Any]:
    method_statuses = run_status.get("validation_method_status") or {}
    completed_methods = [method for method, status in method_statuses.items() if status == "completed"]
    skipped_methods = [method for method, status in method_statuses.items() if status == "skipped"]
    failed_methods = [method for method, status in method_statuses.items() if status == "failed"]
    return {
        "mode": "real_r",
        "completed_methods": completed_methods,
        "skipped_methods": skipped_methods,
        "failed_methods": failed_methods,
        "validation_consistency_score": run_status.get("validation_consistency_score"),
        "validation_consistency_status": run_status.get("validation_consistency_status"),
    }
