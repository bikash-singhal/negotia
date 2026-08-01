import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app.api.dependencies import (
    get_current_user,
    get_negotiation_engine,
    get_negotiation_service,
)
from app.core.observability import log_event
from app.domains.debrief.exceptions import NoCoachObservationsError
from app.domains.negotiation.exceptions import (
    InvalidNegotiationStatusTransitionError,
    NegotiationCompletionLatestTurnFromUserError,
    NegotiationCompletionRequiresExchangeError,
    NegotiationCompletionWithoutTurnsError,
    ScenarioNotFoundError,
)
from app.domains.negotiation.schemas import (
    NegotiationCompletionResponse,
    NegotiationDebriefResponse,
    NegotiationSessionCreate,
    NegotiationSessionResponse,
    NegotiationStrategyResponse,
)
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.exceptions import (
    EmptyOpponentResponseError,
    NegotiationSessionNotFoundError,
    OpponentResponseInProgressError,
    OpponentResponseOutOfSequenceError,
    OpponentResponseRequiresUserTurnError,
)
from app.domains.negotiation_turn.schemas import NegotiationTurnResponse
from app.domains.user.models import User
from app.services.negotiation_engine import (
    NegotiationEngine,
    NegotiationResponseStream,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/negotiations/{session_id}/complete",
    response_model=NegotiationCompletionResponse,
    status_code=status.HTTP_200_OK,
)
def complete_negotiation(
    session_id: UUID,
    engine: Annotated[NegotiationEngine, Depends(get_negotiation_engine)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NegotiationCompletionResponse:
    try:
        result = engine.complete_session(session_id, current_user.id)
    except NegotiationSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except (
        InvalidNegotiationStatusTransitionError,
        NegotiationCompletionWithoutTurnsError,
        NegotiationCompletionLatestTurnFromUserError,
        NegotiationCompletionRequiresExchangeError,
        NoCoachObservationsError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None

    debrief_record = result.debrief_record
    strategy_record = result.strategy_record
    memory_record = result.memory_record
    return NegotiationCompletionResponse(
        session_id=result.session.id,
        status=result.session.status,
        completed_at=result.session.updated_at,
        debrief=NegotiationDebriefResponse.model_validate(debrief_record.debrief),
        observation_count=debrief_record.observation_count,
        debrief_id=debrief_record.id,
        debrief_created_at=debrief_record.created_at,
        strategy=NegotiationStrategyResponse.model_validate(strategy_record.strategy),
        strategy_id=strategy_record.id,
        strategy_created_at=strategy_record.created_at,
        memory=memory_record.memory if memory_record is not None else None,
        memory_id=memory_record.id if memory_record is not None else None,
        memory_created_at=(
            memory_record.created_at if memory_record is not None else None
        ),
    )


@router.post(
    "/negotiations/{session_id}/opponent-response",
    response_model=NegotiationTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_opponent_response(
    session_id: UUID,
    engine: Annotated[NegotiationEngine, Depends(get_negotiation_engine)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NegotiationTurnResponse:
    try:
        turn = engine.generate_response(session_id, current_user.id)
    except (NegotiationSessionNotFoundError, ScenarioNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except (
        OpponentResponseRequiresUserTurnError,
        OpponentResponseOutOfSequenceError,
        OpponentResponseInProgressError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    except EmptyOpponentResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from None

    return NegotiationTurnResponse.model_validate(turn)


@router.post(
    "/negotiations/{session_id}/opponent-response/stream",
    status_code=status.HTTP_200_OK,
)
def stream_opponent_response(
    session_id: UUID,
    request: Request,
    engine: Annotated[NegotiationEngine, Depends(get_negotiation_engine)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    try:
        response_stream = engine.start_response_stream(session_id, current_user.id)
    except (NegotiationSessionNotFoundError, ScenarioNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except (
        OpponentResponseRequiresUserTurnError,
        OpponentResponseOutOfSequenceError,
        OpponentResponseInProgressError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None

    return StreamingResponse(
        _opponent_response_events(request, session_id, response_stream),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
        background=BackgroundTask(response_stream.close),
    )


async def _opponent_response_events(
    request: Request,
    session_id: UUID,
    response_stream: NegotiationResponseStream,
) -> AsyncIterator[str]:
    generated_chunks: list[str] = []
    try:
        yield _ndjson_event({"type": "started"})
        async for chunk in iterate_in_threadpool(response_stream.chunks()):
            if await request.is_disconnected():
                return
            generated_chunks.append(chunk)
            yield _ndjson_event({"type": "delta", "text": chunk})

        if await request.is_disconnected():
            return

        turn = await run_in_threadpool(
            response_stream.complete,
            "".join(generated_chunks),
        )
        response = NegotiationTurnResponse.model_validate(turn)
        yield _ndjson_event(
            {
                "type": "completed",
                "turn": response.model_dump(mode="json"),
            }
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - headers already sent; emit safe event
        code, message = _safe_stream_error(exc)
        log_event(
            logger,
            logging.ERROR,
            "opponent_response_stream_failed",
            operation="opponent_response_stream",
            session_id=session_id,
            outcome="failure",
            message=(f"Opponent response stream failed ({type(exc).__name__})."),
        )
        yield _ndjson_event(
            {
                "type": "error",
                "code": code,
                "message": message,
            }
        )
    finally:
        response_stream.close()


def _safe_stream_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, EmptyOpponentResponseError):
        return (
            "empty_opponent_response",
            "The opponent returned no response. Please try again.",
        )
    if isinstance(
        exc,
        (OpponentResponseOutOfSequenceError, OpponentResponseInProgressError),
    ):
        return (
            "opponent_response_conflict",
            "The conversation changed while the response was generated. Please retry.",
        )
    return (
        "opponent_stream_failed",
        "The opponent response could not be generated. Please try again.",
    )


def _ndjson_event(event: dict[str, object]) -> str:
    return json.dumps(jsonable_encoder(event), separators=(",", ":")) + "\n"


@router.get(
    "/negotiations",
    response_model=list[NegotiationSessionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_negotiations(
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[NegotiationSessionResponse]:
    return [
        NegotiationSessionResponse.model_validate(session)
        for session in service.list_sessions(current_user.id)
    ]


@router.get(
    "/negotiations/{session_id}",
    response_model=NegotiationSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_negotiation(
    session_id: UUID,
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NegotiationSessionResponse:
    session = service.get_session(session_id, current_user.id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Negotiation session with id '{session_id}' was not found.",
        )

    return NegotiationSessionResponse.model_validate(session)


@router.post(
    "/negotiations",
    response_model=NegotiationSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_negotiation(
    request: NegotiationSessionCreate,
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NegotiationSessionResponse:
    try:
        session = service.create_session(request, current_user.id)
    except ScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None

    return NegotiationSessionResponse.model_validate(session)
