from uuid import UUID

import pytest

from app.domains.user.exceptions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
)
from app.domains.user.repository import UserRepository
from app.domains.user.schemas import UserLogin, UserRegister
from app.domains.user.service import UserService
from app.security.passwords import PasswordHasher
from app.security.tokens import AccessTokenManager

SECRET = "test-secret-that-is-not-used-in-production"


@pytest.fixture
def service() -> UserService:
    return UserService(
        UserRepository(),
        PasswordHasher(rounds=4),
        AccessTokenManager(SECRET, 30),
    )


def test_register_hashes_password_and_never_stores_plaintext(
    service: UserService,
) -> None:
    user = service.register(UserRegister(username="negotiator", password="secure-pass"))

    assert user.password_hash != "secure-pass"
    assert user.password_hash.startswith("$2b$")
    assert service._password_hasher.verify("secure-pass", user.password_hash)


def test_register_rejects_duplicate_username(service: UserService) -> None:
    request = UserRegister(username="negotiator", password="secure-pass")
    service.register(request)

    with pytest.raises(UsernameAlreadyExistsError):
        service.register(request)


def test_login_returns_token_for_valid_credentials(service: UserService) -> None:
    user = service.register(UserRegister(username="negotiator", password="secure-pass"))

    token = service.login(UserLogin(username="negotiator", password="secure-pass"))

    assert service._access_token_manager.get_subject(token) == user.id


@pytest.mark.parametrize(
    ("username", "password"),
    [("missing-user", "secure-pass"), ("negotiator", "invalid-password")],
)
def test_login_rejects_invalid_credentials(
    service: UserService,
    username: str,
    password: str,
) -> None:
    service.register(UserRegister(username="negotiator", password="secure-pass"))

    with pytest.raises(InvalidCredentialsError):
        service.login(UserLogin(username=username, password=password))


def test_authenticated_user_must_still_exist(service: UserService) -> None:
    token = service._access_token_manager.create(UUID(int=42))

    with pytest.raises(InvalidAccessTokenError):
        service.get_authenticated_user(token)
