from fastapi import FastAPI

from backend.app.api.task_routes import router as task_router


app = FastAPI(
    title="Bioinformatics Agent Backend",
    version="0.2.0",
)

app.include_router(task_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "bioinformatics-agent-backend",
        "phase": "phase-2-api-skeleton",
    }
