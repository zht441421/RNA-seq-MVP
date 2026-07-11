import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api.task_routes import router as task_router
from backend.app.config import get_api_key_auth_settings
from backend.app.config import get_request_hardening_settings


REQUEST_TOO_LARGE_RESPONSE = {
    "detail": {
        "code": "REQUEST_BODY_TOO_LARGE",
        "message": "Request body exceeds the configured limit.",
    }
}


class _RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """ASGI body guard that avoids buffering a second copy of the request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = get_request_hardening_settings().max_request_bytes
        if limit <= 0:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", ()))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                # Let the application/server handle a malformed header while
                # still verifying the actual stream below.
                pass

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope, receive, send):
        response = JSONResponse(status_code=413, content=REQUEST_TOO_LARGE_RESPONSE)
        await response(scope, receive, send)


app = FastAPI(
    title="Bioinformatics Agent Backend",
    version="0.2.0",
)

app.include_router(task_router)

# Added before the decorator middleware so API-key authentication remains the
# outer layer and has deterministic precedence for protected task endpoints.
app.add_middleware(RequestBodyLimitMiddleware)


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
