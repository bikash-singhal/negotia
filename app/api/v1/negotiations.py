from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_negotiation_service
from app.domains.negotiation.exceptions import ScenarioNotFoundError
from app.domains.negotiation.schemas import (
    NegotiationSessionCreate,
    NegotiationSessionResponse,
)
from app.domains.negotiation.service import NegotiationService

router = APIRouter()


@router.get(
    "/negotiations",
    response_model=list[NegotiationSessionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_negotiations(
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
) -> list[NegotiationSessionResponse]:
    return [
        NegotiationSessionResponse.model_validate(session)
        for session in service.list_sessions()
    ]


@router.get(
    "/negotiations/{session_id}",
    response_model=NegotiationSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_negotiation(
    session_id: UUID,
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
) -> NegotiationSessionResponse:
    session = service.get_session(session_id)
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
) -> NegotiationSessionResponse:
    try:
        session = service.create_session(request)
    except ScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None

    return NegotiationSessionResponse.model_validate(session)
