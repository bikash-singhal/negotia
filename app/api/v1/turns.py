from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_negotiation_turn_service
from app.domains.negotiation_turn.exceptions import (
    NegotiationSessionNotFoundError,
)
from app.domains.negotiation_turn.schemas import (
    NegotiationTurnCreate,
    NegotiationTurnResponse,
)
from app.domains.negotiation_turn.service import NegotiationTurnService

router = APIRouter()


@router.post(
    "/turns",
    response_model=NegotiationTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_turn(
    request: NegotiationTurnCreate,
    service: Annotated[
        NegotiationTurnService,
        Depends(get_negotiation_turn_service),
    ],
) -> NegotiationTurnResponse:
    try:
        turn = service.create_turn(request)
    except NegotiationSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None

    return NegotiationTurnResponse.model_validate(turn)


@router.get(
    "/turns/{turn_id}",
    response_model=NegotiationTurnResponse,
    status_code=status.HTTP_200_OK,
)
async def get_turn(
    turn_id: UUID,
    service: Annotated[
        NegotiationTurnService,
        Depends(get_negotiation_turn_service),
    ],
) -> NegotiationTurnResponse:
    turn = service.get_turn(turn_id)
    if turn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Negotiation turn with id '{turn_id}' was not found.",
        )

    return NegotiationTurnResponse.model_validate(turn)


@router.get(
    "/negotiations/{session_id}/turns",
    response_model=list[NegotiationTurnResponse],
    status_code=status.HTTP_200_OK,
)
async def list_turns(
    session_id: UUID,
    service: Annotated[
        NegotiationTurnService,
        Depends(get_negotiation_turn_service),
    ],
) -> list[NegotiationTurnResponse]:
    try:
        turns = service.list_turns(session_id)
    except NegotiationSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None

    return [NegotiationTurnResponse.model_validate(turn) for turn in turns]
