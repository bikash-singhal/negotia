from uuid import UUID

from app.domains.user.exceptions import UsernameAlreadyExistsError
from app.domains.user.models import User


class UserRepository:
    def __init__(self) -> None:
        self._users_by_id: dict[UUID, User] = {}
        self._users_by_username: dict[str, User] = {}

    def create(self, user: User) -> User:
        if user.username in self._users_by_username:
            raise UsernameAlreadyExistsError(user.username)

        self._users_by_id[user.id] = user
        self._users_by_username[user.username] = user
        return user

    def get(self, user_id: UUID) -> User | None:
        return self._users_by_id.get(user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._users_by_username.get(username)
