from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_current_user,
    get_negotiation_engine,
    get_negotiation_service,
)
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
    OpponentResponseOutOfSequenceError,
    OpponentResponseRequiresUserTurnError,
)
from app.domains.negotiation_turn.schemas import NegotiationTurnResponse
from app.domains.user.models import User
from app.services.negotiation_engine import NegotiationEngine

router = APIRouter()


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
