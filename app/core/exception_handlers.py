import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.core.observability import log_event
from app.core.request_context import REQUEST_ID_HEADER, request_id_from_request

logger = logging.getLogger(__name__)


async def _handle_app_exception(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
        headers=_request_id_headers(request),
    )


async def _handle_http_exception(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    error_code = {
        404: "not_found",
        405: "method_not_allowed",
    }.get(exc.status_code, "http_error")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": str(exc.detail),
            }
        },
        headers=_request_id_headers(request, exc.headers),
    )


async def _handle_validation_exception(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": jsonable_encoder(exc.errors()),
            }
        },
        headers=_request_id_headers(request),
    )


async def _handle_unexpected_exception(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    request_id = request_id_from_request(request)
    safe_exception = RuntimeError("Unexpected application error")
    log_event(
        logger,
        logging.ERROR,
        "unexpected_exception",
        message=f"Unexpected application error ({type(exc).__name__})",
        request_id=request_id,
        route=request.url.path,
        outcome="failure",
        exc_info=(RuntimeError, safe_exception, exc.__traceback__),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred",
            }
        },
        headers={REQUEST_ID_HEADER: request_id},
    )


def _request_id_headers(
    request: Request,
    headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = request_id_from_request(request)
    return response_headers


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        AppException,
        _handle_app_exception,  # pyright: ignore[reportArgumentType]
    )
    app.add_exception_handler(
        StarletteHTTPException,
        _handle_http_exception,  # pyright: ignore[reportArgumentType]
    )
    app.add_exception_handler(
        RequestValidationError,
        _handle_validation_exception,  # pyright: ignore[reportArgumentType]
    )
    app.add_exception_handler(Exception, _handle_unexpected_exception)
