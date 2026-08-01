from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.domains.user.exceptions import (
    ExpiredAccessTokenError,
    InvalidAccessTokenError,
)

JWT_ALGORITHM = "HS256"


class AccessTokenManager:
    def __init__(self, secret_key: str, expire_minutes: int) -> None:
        self._secret_key = secret_key
        self._expire_minutes = expire_minutes

    def create(self, user_id: UUID) -> str:
        issued_at = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": str(user_id),
                "iat": issued_at,
                "exp": issued_at + timedelta(minutes=self._expire_minutes),
            },
            self._secret_key,
            algorithm=JWT_ALGORITHM,
        )

    def get_subject(self, token: str) -> UUID:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[JWT_ALGORITHM],
            )
        except ExpiredSignatureError:
            raise ExpiredAccessTokenError() from None
        except InvalidTokenError:
            raise InvalidAccessTokenError() from None

        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise InvalidAccessTokenError()

        try:
            return UUID(subject)
        except ValueError:
            raise InvalidAccessTokenError() from None
