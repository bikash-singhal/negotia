from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.domains.user.exceptions import (
    ExpiredAccessTokenError,
    InvalidAccessTokenError,
)
from app.security.tokens import JWT_ALGORITHM, AccessTokenManager

SECRET = "test-secret-that-is-not-used-in-production"


def test_access_token_round_trip() -> None:
    user_id = uuid4()
    manager = AccessTokenManager(SECRET, 30)

    assert manager.get_subject(manager.create(user_id)) == user_id


def test_access_token_uses_configured_expiration() -> None:
    manager = AccessTokenManager(SECRET, 45)

    token = manager.create(uuid4())
    payload = jwt.decode(token, SECRET, algorithms=[JWT_ALGORITHM])

    assert payload["exp"] - payload["iat"] == 45 * 60


def test_expired_access_token_is_rejected() -> None:
    manager = AccessTokenManager(SECRET, 30)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        SECRET,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(ExpiredAccessTokenError):
        manager.get_subject(token)


@pytest.mark.parametrize(
    "token",
    ["not-a-token", jwt.encode({}, SECRET, algorithm=JWT_ALGORITHM)],
)
def test_invalid_access_token_is_rejected(token: str) -> None:
    manager = AccessTokenManager(SECRET, 30)

    with pytest.raises(InvalidAccessTokenError):
        manager.get_subject(token)
