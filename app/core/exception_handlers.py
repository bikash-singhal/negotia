import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


async def _handle_app_exception(
    _request: Request,
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
    )


async def _handle_http_exception(
    _request: Request,
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
        headers=exc.headers,
    )


async def _handle_validation_exception(
    _request: Request,
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
    )


async def _handle_unexpected_exception(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception("Unexpected application error", exc_info=exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred",
            }
        },
    )


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
