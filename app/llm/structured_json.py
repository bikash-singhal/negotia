import json
import logging
from collections.abc import Callable

from pydantic import BaseModel, ValidationError

from app.core.observability import log_event

ExceptionFactory = Callable[[], Exception]


def parse_structured_json[PayloadT: BaseModel](
    raw_response: str,
    payload_type: type[PayloadT],
    *,
    logger: logging.Logger,
    operation: str,
    empty_response_error: ExceptionFactory,
    invalid_json_error: ExceptionFactory,
    invalid_data_error: ExceptionFactory,
    session_id: object | None = None,
) -> PayloadT:
    response = raw_response.strip()
    if not response:
        _log_parse_failure(
            logger,
            operation,
            session_id=session_id,
            output_length=len(raw_response),
            fence_detected=False,
            failure_category="empty_output",
        )
        raise empty_response_error()

    normalized_response, fence_detected = _remove_outer_json_fence(response)
    try:
        data = json.loads(normalized_response)
    except json.JSONDecodeError:
        _log_parse_failure(
            logger,
            operation,
            session_id=session_id,
            output_length=len(raw_response),
            fence_detected=fence_detected,
            failure_category="invalid_json",
        )
        raise invalid_json_error() from None

    try:
        return payload_type.model_validate(data)
    except ValidationError:
        _log_parse_failure(
            logger,
            operation,
            session_id=session_id,
            output_length=len(raw_response),
            fence_detected=fence_detected,
            failure_category="invalid_schema",
        )
        raise invalid_data_error() from None


def _remove_outer_json_fence(response: str) -> tuple[str, bool]:
    fence_detected = "```" in response
    if not response.startswith("```") or not response.endswith("```"):
        return response, fence_detected

    opening_line, separator, fenced_content = response.partition("\n")
    if not separator or opening_line.strip().lower() not in {"```", "```json"}:
        return response, fence_detected

    return fenced_content.removesuffix("```").strip(), True


def _log_parse_failure(
    logger: logging.Logger,
    operation: str,
    *,
    session_id: object | None,
    output_length: int,
    fence_detected: bool,
    failure_category: str,
) -> None:
    log_event(
        logger,
        logging.WARNING,
        "structured_output_parse_failed",
        operation=operation,
        session_id=session_id,
        stage="structured_output_parsing",
        output_length=output_length,
        fence_detected=fence_detected,
        failure_category=failure_category,
        outcome="failure",
    )
