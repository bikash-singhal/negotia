import logging
from contextvars import ContextVar, Token
from time import perf_counter
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

_STRUCTURED_DEFAULTS: dict[str, object] = {
    "request_id": "-",
    "event": "-",
    "operation": "-",
    "route": "-",
    "session_id": "-",
    "stage": "-",
    "provider": "-",
    "model_id": "-",
    "duration_ms": "-",
    "outcome": "-",
}


class StructuredContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for field, default in _STRUCTURED_DEFAULTS.items():
            if not hasattr(record, field):
                setattr(record, field, default)
        if getattr(record, "request_id", "-") == "-":
            record.__dict__["request_id"] = get_request_id() or "-"
        return True


def set_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()


def elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    message: str | None = None,
    request_id: str | None = None,
    operation: str | None = None,
    route: str | None = None,
    session_id: object | None = None,
    stage: str | None = None,
    provider: str | None = None,
    model_id: str | None = None,
    duration_ms: float | None = None,
    outcome: str | None = None,
    exc_info: Any = None,
) -> None:
    try:
        extra = {
            "request_id": request_id or get_request_id() or "-",
            "event": event,
            "operation": operation or "-",
            "route": route or "-",
            "session_id": str(session_id) if session_id is not None else "-",
            "stage": stage or "-",
            "provider": provider or "-",
            "model_id": model_id or "-",
            "duration_ms": duration_ms if duration_ms is not None else "-",
            "outcome": outcome or "-",
        }
        logger.log(
            level,
            message or event,
            extra=extra,
            exc_info=exc_info,
        )
    except Exception:  # noqa: BLE001 - observability must never alter execution
        return
