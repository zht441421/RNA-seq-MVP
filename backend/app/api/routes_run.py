from fastapi import APIRouter, HTTPException

from backend.app.config import get_settings
from backend.app.models.project import ProjectStatus
from backend.app.models.schemas import RunRequest, RunResponse
from backend.app.reports.evidence_package import collect_existing_artifacts, create_evidence_package
from backend.app.runners.docker_r_bulk_rnaseq_runner import DockerRBulkRNASeqRunner
from backend.app.runners.pipeline_runner import MockPipelineRunner
from backend.app.runners.r_bulk_rnaseq_runner import RBulkRNASeqRunner
from backend.app.services.artifact_service import STORE
from backend.app.services.reliability_service import assess_reliability


router = APIRouter(tags=["run"])


@router.post("/projects/{project_id}/run", response_model=RunResponse)
def run_project(project_id: str, request: RunRequest = RunRequest()) -> RunResponse:
    return execute_project_run(project_id=project_id, plan_id=request.plan_id)


def execute_project_run(project_id: str, plan_id: str = None, run_mode_override: str = None) -> RunResponse:
    _require_project(project_id)
    config = STORE.analysis_configs.get(project_id)
    qc_report = STORE.qc_reports.get(project_id)
    plan = STORE.plans.get(project_id)
    if not config:
        raise HTTPException(status_code=400, detail="No analysis config is available. Run QC or plan first.")
    if not qc_report:
        raise HTTPException(status_code=400, detail="QC report is required before run.")
    if not plan:
        raise HTTPException(status_code=400, detail="Confirmed analysis plan is required before run.")
    if plan_id and plan_id != plan.plan_id:
        raise HTTPException(status_code=400, detail="Requested plan_id does not match active plan.")
    if not plan.confirmed:
        raise HTTPException(status_code=400, detail="Analysis plan must be confirmed before run.")
    if not qc_report.passed:
        raise HTTPException(status_code=400, detail="QC has blocking issues. Resolve them before running analysis.")

    STORE.update_status(project_id, ProjectStatus.RUNNING)
    run_mode = _normalize_run_mode(run_mode_override or get_settings().run_mode)
    STORE.artifacts[project_id] = []

    if run_mode == "real_r":
        runner = RBulkRNASeqRunner()
        run_result = runner.run(config=config, plan=plan)
        reliability = assess_reliability(
            qc_report=qc_report,
            validation_status=run_result.get("validation_status", {}),
            plan_confirmed=plan.confirmed,
            audit_artifacts_complete=_path_exists(run_result.get("audit_log_path")),
            run_status=run_result.get("run_status", {}),
        )
    elif run_mode == "docker_r":
        runner = DockerRBulkRNASeqRunner()
        run_result = runner.run(config=config, plan=plan)
        reliability = assess_reliability(
            qc_report=qc_report,
            validation_status=run_result.get("validation_status", {}),
            plan_confirmed=plan.confirmed,
            audit_artifacts_complete=_path_exists(run_result.get("audit_log_path")),
            run_status=run_result.get("run_status", {}),
        )
    elif run_mode == "mock":
        runner = MockPipelineRunner()
        run_result = runner.run(config=config, plan=plan, qc_report=qc_report)
        reliability = assess_reliability(
            qc_report=qc_report,
            validation_status=run_result.get("validation_status", {}),
            plan_confirmed=plan.confirmed,
            audit_artifacts_complete=True,
        )
    else:
        raise HTTPException(status_code=500, detail=f"Unsupported RUN_MODE: {run_mode}")

    manifest = create_evidence_package(
        project_id=project_id,
        context={
            "project": STORE.require_project(project_id),
            "config": config,
            "plan": plan,
            "qc_report": qc_report,
            "reliability": reliability,
            "run_result": run_result,
        },
    )
    STORE.artifacts[project_id] = []
    for artifact in collect_existing_artifacts(_as_path(manifest["artifact_root"])):
        STORE.register_artifact_file(project_id, _as_path(artifact["path"]), "evidence_package_file")
    STORE.reliability[project_id] = reliability
    STORE.results[project_id] = {
        "execution_mode": run_mode,
        "primary_method": plan.primary_method,
        "validation_methods": plan.validation_methods,
        "result_available": run_mode in {"real_r", "docker_r"} and run_result.get("status") == "completed",
        "message": _result_message(run_mode, run_result),
        "run_status": run_result.get("run_status"),
        "evidence_manifest_path": str(_as_path(manifest["artifact_root"]) / "manifest.json"),
    }
    final_status = ProjectStatus.COMPLETED if _run_completed(run_result) else ProjectStatus.FAILED
    project = STORE.update_status(project_id, final_status)
    return RunResponse(
        project_id=project_id,
        status=project.status,
        plan=plan,
        reliability=reliability,
        artifacts=STORE.list_artifacts(project_id),
        result_summary=STORE.results[project_id],
    )


def _require_project(project_id: str) -> None:
    try:
        STORE.require_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc


def _as_path(path: str):
    from pathlib import Path

    return Path(path)


def _path_exists(path: str) -> bool:
    if not path:
        return False
    return _as_path(path).exists()


def _result_message(run_mode: str, run_result: dict) -> str:
    if run_mode == "mock":
        return "Mock run completed. No real differential expression result was generated."
    if run_mode == "docker_r":
        if run_result.get("status") == "completed":
            return "Dockerized R differential expression run completed."
        return "Dockerized R differential expression run failed. See run_status and Docker stderr artifacts."
    if run_result.get("status") == "completed":
        return "Real R differential expression run completed."
    return "Real R differential expression run failed. See run_status and stderr artifacts."


def _run_completed(run_result: dict) -> bool:
    return run_result.get("status") in {"completed", "mock_completed"}


def _normalize_run_mode(run_mode: str) -> str:
    aliases = {
        "r_docker": "docker_r",
        "real_r_docker": "docker_r",
    }
    return aliases.get(run_mode, run_mode)
