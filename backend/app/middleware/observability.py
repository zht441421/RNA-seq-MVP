import time
from uuid import uuid4

from fastapi.responses import JSONResponse

from backend.app.utils.logging import SERVICE_NAME
from backend.app.utils.logging import get_logger
from backend.app.utils.logging import request_id_context


logger = get_logger(__name__)
REQUEST_ID_HEADER = b"x-request-id"


class RequestObservabilityMiddleware:
    """Add request correlation and lightweight operational request logs."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message):
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = list(message.get("headers", ()))
                headers = [
                    (name, value)
                    for name, value in headers
                    if name.lower() != REQUEST_ID_HEADER
                ]
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            self._log(
                "request_failed", scope, request_id, 500, started, level="error"
            )
            if response_started:
                raise
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={"X-Request-ID": request_id},
            )
            await response(scope, receive, send)
            return
        finally:
            request_id_context.reset(token)

        self._log("request_completed", scope, request_id, status_code, started)

    @staticmethod
    def _log(message, scope, request_id, status_code, started, level="info"):
        route = scope.get("route")
        route_path = getattr(route, "path", None) or scope.get("path", "")
        task_id = (scope.get("path_params") or {}).get("task_id")
        fields = {
            "service": SERVICE_NAME,
            "request_id": request_id,
            "route": route_path,
            "method": scope.get("method"),
            "status_code": status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        if task_id:
            fields["task_id"] = task_id
        getattr(logger, level)(message, extra=fields)
