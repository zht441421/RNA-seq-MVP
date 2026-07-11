import asyncio
import math
import time

from fastapi.responses import JSONResponse

from backend.app.config import get_rate_limit_settings


class InMemoryRateLimitMiddleware:
    """Optional fixed-window limiter designed for later backend replacement."""

    def __init__(self, app):
        self.app = app
        self._counters: dict[str, tuple[float, int]] = {}
        self._lock = asyncio.Lock()
        self._configuration: tuple[int, int, str] | None = None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            settings = get_rate_limit_settings()
        except ValueError:
            response = JSONResponse(
                status_code=503,
                content={"detail": "Service rate limiting is unavailable"},
            )
            await response(scope, receive, send)
            return

        path = scope.get("path", "")
        if not settings.enabled or path in settings.exempt_paths:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        now = time.monotonic()

        async with self._lock:
            configuration = (
                settings.requests,
                settings.window_seconds,
                settings.scope,
            )
            if configuration != self._configuration:
                self._counters.clear()
                self._configuration = configuration
            window_start, count = self._counters.get(client_ip, (now, 0))
            if now - window_start >= settings.window_seconds:
                window_start, count = now, 0

            if count >= settings.requests:
                retry_after = max(
                    1, math.ceil(settings.window_seconds - (now - window_start))
                )
            else:
                self._counters[client_ip] = (window_start, count + 1)
                retry_after = 0

        if retry_after:
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests. Please retry later.",
                        "retry_after_seconds": retry_after,
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
