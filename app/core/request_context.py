import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.core.observability import (
    elapsed_ms,
    log_event,
    reset_request_id,
    set_request_id,
)

REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger(__name__)


async def request_context_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
    request.state.request_id = request_id
    token = set_request_id(request_id)
    started_at = perf_counter()
    operation = f"{request.method} {request.url.path}"
    log_event(
        logger,
        logging.INFO,
        "request_started",
        operation=operation,
        route=request.url.path,
    )

    try:
        response = await call_next(request)
    except Exception:
        log_event(
            logger,
            logging.ERROR,
            "request_failed",
            operation=operation,
            route=_route_path(request),
            duration_ms=elapsed_ms(started_at),
            outcome="failure",
        )
        raise
    else:
        response.headers[REQUEST_ID_HEADER] = request_id
        log_event(
            logger,
            logging.INFO,
            "request_completed",
            operation=operation,
            route=_route_path(request),
            duration_ms=elapsed_ms(started_at),
            outcome=str(response.status_code),
        )
        return response
    finally:
        reset_request_id(token)


def request_id_from_request(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    return request.headers.get(REQUEST_ID_HEADER) or str(uuid4())


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else request.url.path
