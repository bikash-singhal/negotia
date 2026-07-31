import asyncio
import logging
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import Request, Response
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_negotiation_service
from app.core.observability import get_request_id, reset_request_id, set_request_id
from app.core.request_context import REQUEST_ID_HEADER, request_context_middleware
from app.database.unit_of_work import SQLCompletionUnitOfWork
from app.llm.observability import generate_with_observability
from app.main import app


def _events(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        event
        for record in caplog.records
        if isinstance((event := getattr(record, "event", None)), str)
    ]


def test_request_generates_request_id_and_returns_response_header() -> None:
    with TestClient(app) as client:
        first_response = client.get("/api/v1/health")
        second_response = client.get("/api/v1/health")

    first_request_id = first_response.headers[REQUEST_ID_HEADER]
    second_request_id = second_response.headers[REQUEST_ID_HEADER]
    assert UUID(first_request_id)
    assert UUID(second_request_id)
    assert first_request_id != second_request_id


def test_request_preserves_incoming_request_id() -> None:
    request_id = "client-request-id"

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health",
            headers={REQUEST_ID_HEADER: request_id},
        )

    assert response.headers[REQUEST_ID_HEADER] == request_id


def test_request_ids_are_isolated_between_concurrent_contexts() -> None:
    async def observe(request_id: str) -> str | None:
        token = set_request_id(request_id)
        try:
            await asyncio.sleep(0)
            return get_request_id()
        finally:
            reset_request_id(token)

    async def observe_together() -> tuple[str | None, str | None]:
        first, second = await asyncio.gather(
            observe("request-one"),
            observe("request-two"),
        )
        return first, second

    assert asyncio.run(observe_together()) == ("request-one", "request-two")
    assert get_request_id() is None


def test_request_context_is_reset_after_success_and_failure() -> None:
    def request() -> Request:
        return Request(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/test",
                "raw_path": b"/test",
                "query_string": b"",
                "root_path": "",
                "headers": [],
                "client": ("test-client", 1),
                "server": ("test-server", 80),
                "state": {},
            }
        )

    async def exercise() -> None:
        async def succeed(_request: Request) -> Response:
            assert get_request_id() is not None
            return Response()

        async def fail(_request: Request) -> Response:
            assert get_request_id() is not None
            raise RuntimeError("request failed")

        await request_context_middleware(request(), succeed)
        assert get_request_id() is None

        with pytest.raises(RuntimeError, match="request failed"):
            await request_context_middleware(request(), fail)
        assert get_request_id() is None

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/health",
        "/health",
        "/api/v1/negotiations/not-a-uuid",
    ],
)
def test_normal_and_handled_error_responses_include_request_id(path: str) -> None:
    with TestClient(app) as client:
        response = client.get(path)

    assert UUID(response.headers[REQUEST_ID_HEADER])


def test_unexpected_exception_keeps_safe_response_and_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request_id = "failed-request-id"
    failing_service = MagicMock()
    failing_service.list_sessions.side_effect = RuntimeError(
        "internal failure must not reach the client"
    )
    app.dependency_overrides[get_negotiation_service] = lambda: failing_service
    caplog.set_level(logging.ERROR)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/negotiations",
                headers={REQUEST_ID_HEADER: request_id},
            )
    finally:
        app.dependency_overrides.pop(get_negotiation_service, None)

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred",
        }
    }
    assert response.headers[REQUEST_ID_HEADER] == request_id
    exception_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "unexpected_exception"
    ]
    assert len(exception_records) == 1
    assert getattr(exception_records[0], "request_id", None) == request_id
    assert exception_records[0].exc_info is not None
    assert sum(record.exc_info is not None for record in caplog.records) == 1
    assert "internal failure must not reach the client" not in caplog.text


def test_llm_observability_does_not_log_prompts_or_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = MagicMock()
    provider.generate.return_value = "sensitive raw model response"
    caplog.set_level(logging.DEBUG, logger="tests.observability.llm")
    test_logger = logging.getLogger("tests.observability.llm")

    response = generate_with_observability(
        provider,
        test_logger,
        "test_extraction",
        system_prompt="sensitive hidden scenario context",
        user_prompt="sensitive negotiation turn content",
    )

    assert response == "sensitive raw model response"
    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "sensitive hidden scenario context" not in rendered_logs
    assert "sensitive negotiation turn content" not in rendered_logs
    assert "sensitive raw model response" not in rendered_logs
    assert _events(caplog) == ["llm_request_started", "llm_request_completed"]


def test_llm_provider_call_continues_when_logging_fails() -> None:
    class FailingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            raise RuntimeError("logging failed")

    provider = MagicMock()
    provider.generate.return_value = "provider result"
    test_logger = logging.getLogger("tests.observability.failing_llm_logger")
    handler = FailingHandler()
    previous_level = test_logger.level
    previous_disabled = test_logger.disabled
    test_logger.disabled = False
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)

    try:
        result = generate_with_observability(
            provider,
            test_logger,
            "test_extraction",
            system_prompt="system prompt",
            user_prompt="user prompt",
        )
    finally:
        test_logger.removeHandler(handler)
        test_logger.setLevel(previous_level)
        test_logger.disabled = previous_disabled

    assert result == "provider result"
    provider.generate.assert_called_once_with(
        system_prompt="system prompt",
        user_prompt="user prompt",
    )


def test_unit_of_work_logs_commit_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    database_session = MagicMock(spec=Session)
    caplog.set_level(logging.INFO, logger="app.database.unit_of_work")

    with SQLCompletionUnitOfWork(lambda: database_session) as unit_of_work:
        unit_of_work.commit()

    assert _events(caplog) == ["transaction_started", "transaction_committed"]


def test_unit_of_work_logs_automatic_rollback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    database_session = MagicMock(spec=Session)
    caplog.set_level(logging.INFO, logger="app.database.unit_of_work")

    with (
        pytest.raises(RuntimeError, match="force rollback"),
        SQLCompletionUnitOfWork(lambda: database_session),
    ):
        raise RuntimeError("force rollback")

    assert _events(caplog) == [
        "transaction_started",
        "transaction_failed",
        "transaction_rolled_back",
    ]


def test_unit_of_work_commit_and_close_continue_when_logging_fails() -> None:
    class FailingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            raise RuntimeError("logging failed")

    database_session = MagicMock(spec=Session)
    transaction_logger = logging.getLogger("app.database.unit_of_work")
    handler = FailingHandler()
    previous_level = transaction_logger.level
    previous_disabled = transaction_logger.disabled
    transaction_logger.disabled = False
    transaction_logger.setLevel(logging.INFO)
    transaction_logger.addHandler(handler)

    try:
        with SQLCompletionUnitOfWork(lambda: database_session) as unit_of_work:
            unit_of_work.commit()
    finally:
        transaction_logger.removeHandler(handler)
        transaction_logger.setLevel(previous_level)
        transaction_logger.disabled = previous_disabled

    database_session.commit.assert_called_once_with()
    database_session.close.assert_called_once_with()


def test_unit_of_work_rollback_and_close_continue_when_logging_fails() -> None:
    class FailingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            raise RuntimeError("logging failed")

    database_session = MagicMock(spec=Session)
    transaction_logger = logging.getLogger("app.database.unit_of_work")
    handler = FailingHandler()
    previous_level = transaction_logger.level
    previous_disabled = transaction_logger.disabled
    transaction_logger.disabled = False
    transaction_logger.setLevel(logging.INFO)
    transaction_logger.addHandler(handler)

    try:
        with (
            pytest.raises(ValueError, match="business failure"),
            SQLCompletionUnitOfWork(lambda: database_session),
        ):
            raise ValueError("business failure")
    finally:
        transaction_logger.removeHandler(handler)
        transaction_logger.setLevel(previous_level)
        transaction_logger.disabled = previous_disabled

    database_session.rollback.assert_called_once_with()
    database_session.close.assert_called_once_with()
