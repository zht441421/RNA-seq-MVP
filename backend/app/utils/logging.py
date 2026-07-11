from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
from typing import Any


SERVICE_NAME = "bioinformatics-agent-backend"
request_id_context: ContextVar[str | None] = ContextVar(
    "request_id", default=None
)


class StructuredJSONFormatter(logging.Formatter):
    """Minimal JSON formatter for operational application logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", SERVICE_NAME),
            "message": record.getMessage(),
        }
        for field in (
            "request_id",
            "task_id",
            "route",
            "method",
            "status_code",
            "duration_ms",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, separators=(",", ":"), default=str)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(getattr(handler, "_bioinfo_structured", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredJSONFormatter())
        handler._bioinfo_structured = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
