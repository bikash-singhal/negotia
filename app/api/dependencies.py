from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.scenario.service import ScenarioService
from app.domains.user.exceptions import InvalidAccessTokenError
from app.domains.user.models import User
from app.domains.user.service import UserService
from app.services.negotiation_engine import NegotiationEngine

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_scenario_service(request: Request) -> ScenarioService:
    return cast(ScenarioService, request.app.state.scenario_service)


def get_negotiation_service(request: Request) -> NegotiationService:
    return cast(NegotiationService, request.app.state.negotiation_service)


def get_negotiation_turn_service(request: Request) -> NegotiationTurnService:
    return cast(
        NegotiationTurnService,
        request.app.state.negotiation_turn_service,
    )


def get_negotiation_engine(request: Request) -> NegotiationEngine:
    return cast(NegotiationEngine, request.app.state.negotiation_engine)


def get_user_service(request: Request) -> UserService:
    return cast(UserService, request.app.state.user_service)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    try:
        return service.get_authenticated_user(token)
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
