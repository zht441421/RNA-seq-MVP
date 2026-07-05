from fastapi import FastAPI

from backend.app.api.routes_coze import router as coze_router
from backend.app.api.routes_files import router as files_router
from backend.app.api.routes_plan import router as plan_router
from backend.app.api.routes_projects import router as projects_router
from backend.app.api.routes_qc import router as qc_router
from backend.app.api.routes_results import router as results_router
from backend.app.api.routes_run import router as run_router
from backend.app.api.routes_system import router as system_router
from backend.app.api.routes_ui import router as ui_router
from backend.app.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Phase 1 MVP backend for Coze-driven Bulk RNA-seq analysis orchestration.",
)

app.include_router(projects_router)
app.include_router(coze_router)
app.include_router(files_router)
app.include_router(qc_router)
app.include_router(plan_router)
app.include_router(run_router)
app.include_router(results_router)
app.include_router(system_router)
app.include_router(ui_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
