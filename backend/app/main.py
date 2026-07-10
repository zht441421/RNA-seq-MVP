import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api.task_routes import router as task_router
from backend.app.config import get_api_key_auth_settings


app = FastAPI(
    title="Bioinformatics Agent Backend",
    version="0.2.0",
)

app.include_router(task_router)


@app.middleware("http")
async def optional_api_key_auth(request: Request, call_next):
    if not request.url.path.startswith("/task"):
        return await call_next(request)

    try:
        settings = get_api_key_auth_settings()
    except (KeyError, ValueError):
        return JSONResponse(
            status_code=503,
            content={"detail": "Service authentication is unavailable"},
        )

    if not settings.require_api_key:
        return await call_next(request)

    if settings.api_key is None or not settings.api_key.get_secret_value():
        return JSONResponse(
            status_code=503,
            content={"detail": "Service authentication is unavailable"},
        )

    provided_key = request.headers.get(settings.api_key_header)
    expected_key = settings.api_key.get_secret_value()
    if provided_key is None or not hmac.compare_digest(
        provided_key, expected_key
    ):
        return JSONResponse(
            status_code=401,
            content={"detail": "Valid API key required"},
        )

    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "bioinformatics-agent-backend",
        "phase": "phase-2-api-skeleton",
    }
