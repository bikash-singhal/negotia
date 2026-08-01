from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user, get_user_service
from app.domains.user.exceptions import (
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
)
from app.domains.user.models import User
from app.domains.user.schemas import (
    AccessTokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.domains.user.service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: UserRegister,
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    try:
        user = service.register(request)
    except UsernameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    request: UserLogin,
    service: Annotated[UserService, Depends(get_user_service)],
) -> AccessTokenResponse:
    try:
        access_token = service.login(request)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return AccessTokenResponse(access_token=access_token)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)
