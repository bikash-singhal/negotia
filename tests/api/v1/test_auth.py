from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient

from app.domains.user.repository import UserRepository
from app.domains.user.service import UserService
from app.main import app
from app.security.passwords import PasswordHasher
from app.security.tokens import JWT_ALGORITHM, AccessTokenManager

SECRET = "test-secret-that-is-not-used-in-production"


@dataclass(frozen=True)
class AuthContext:
    repository: UserRepository
    token_manager: AccessTokenManager


@pytest.fixture
def auth_context() -> AuthContext:
    return AuthContext(
        repository=UserRepository(),
        token_manager=AccessTokenManager(SECRET, 30),
    )


@pytest.fixture
def client(auth_context: AuthContext) -> Iterator[TestClient]:
    previous_service = app.state.user_service
    app.state.user_service = UserService(
        auth_context.repository,
        PasswordHasher(rounds=4),
        auth_context.token_manager,
    )
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.state.user_service = previous_service


def _register(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "negotiator", "password": "secure-pass"},
    )
    assert response.status_code == 201
    return response.json()


def _parse_uuid(value: object) -> UUID:
    assert isinstance(value, str)
    return UUID(value)


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "negotiator", "password": "secure-pass"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    return body["access_token"]


def test_registration_returns_public_user_and_stores_only_hash(
    client: TestClient,
    auth_context: AuthContext,
) -> None:
    body = _register(client)

    assert set(body) == {"id", "username", "created_at"}
    assert body["username"] == "negotiator"
    user = auth_context.repository.get(_parse_uuid(body["id"]))
    assert user is not None
    assert user.password_hash != "secure-pass"
    assert user.password_hash.startswith("$2b$")


def test_duplicate_username_returns_conflict(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/api/v1/auth/register",
        json={"username": "negotiator", "password": "another-pass"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Username 'negotiator' is already registered.",
        }
    }


def test_login_success_returns_valid_access_token(
    client: TestClient,
    auth_context: AuthContext,
) -> None:
    registered = _register(client)

    token = _login(client)

    assert auth_context.token_manager.get_subject(token) == _parse_uuid(
        registered["id"]
    )


def test_login_fails_for_unknown_username(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "unknown-user", "password": "secure-pass"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_fails_for_invalid_password(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "negotiator", "password": "incorrect"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid username or password."


def test_me_returns_authenticated_user(client: TestClient) -> None:
    registered = _register(client)
    token = _login(client)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == registered


def test_me_rejects_expired_token(client: TestClient) -> None:
    registered = _register(client)
    token = jwt.encode(
        {
            "sub": str(registered["id"]),
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["message"] == (
        "Could not validate authentication credentials."
    )


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401


def test_me_rejects_unauthorized_request(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Not authenticated",
        }
    }


def test_auth_request_validation_uses_standard_error_shape(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "x", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
