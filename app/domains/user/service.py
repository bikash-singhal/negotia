from datetime import UTC, datetime
from uuid import uuid4

from app.domains.user.exceptions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
)
from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.domains.user.schemas import UserLogin, UserRegister
from app.security.passwords import PasswordHasher
from app.security.tokens import AccessTokenManager


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
        access_token_manager: AccessTokenManager,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._access_token_manager = access_token_manager

    def register(self, request: UserRegister) -> User:
        if self._repository.get_by_username(request.username) is not None:
            raise UsernameAlreadyExistsError(request.username)

        user = User(
            id=uuid4(),
            username=request.username,
            password_hash=self._password_hasher.hash(request.password),
            created_at=datetime.now(UTC),
        )
        return self._repository.create(user)

    def login(self, request: UserLogin) -> str:
        user = self._repository.get_by_username(request.username)
        if user is None or not self._password_hasher.verify(
            request.password,
            user.password_hash,
        ):
            raise InvalidCredentialsError()

        return self._access_token_manager.create(user.id)

    def get_authenticated_user(self, token: str) -> User:
        user_id = self._access_token_manager.get_subject(token)
        user = self._repository.get(user_id)
        if user is None:
            raise InvalidAccessTokenError()
        return user
