from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models.user import UserModel
from app.database.repositories.user import (
    SQLUserRepository,
    user_to_domain,
    user_to_model,
)
from app.domains.user.exceptions import UsernameAlreadyExistsError
from app.domains.user.models import User
from app.domains.user.schemas import UserRegister
from app.domains.user.service import UserService
from app.security.passwords import PasswordHasher
from app.security.tokens import AccessTokenManager

SessionFactory = Callable[[], Session]


def _user(
    *,
    user_id: UUID | None = None,
    username: str = "negotiator",
) -> User:
    return User(
        id=user_id or uuid4(),
        username=username,
        password_hash="$2b$12$stored-password-hash",
        created_at=datetime.now(UTC),
    )


def test_mapping_round_trip() -> None:
    user = _user()

    model = user_to_model(user)
    restored = user_to_domain(model)

    assert isinstance(model, UserModel)
    assert restored == user
    assert restored is not user


def test_create_and_get_by_id_and_username(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLUserRepository(database_session_factory)
    user = _user()

    created = repository.create(user)

    assert created == user
    assert created is not user
    assert repository.get(user.id) == user
    assert repository.get_by_username(user.username) == user


def test_missing_user_returns_none(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLUserRepository(database_session_factory)

    assert repository.get(uuid4()) is None
    assert repository.get_by_username("missing") is None


def test_duplicate_username_raises_domain_exception(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLUserRepository(database_session_factory)
    repository.create(_user())

    with pytest.raises(UsernameAlreadyExistsError):
        repository.create(_user())


def test_duplicate_primary_key_raises_integrity_error_and_preserves_first_user(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLUserRepository(database_session_factory)
    user = repository.create(_user())

    with pytest.raises(IntegrityError):
        repository.create(_user(user_id=user.id, username="another-user"))

    assert repository.get(user.id) == user


def test_persistence_is_visible_through_fresh_repository_instance(
    database_session_factory: SessionFactory,
) -> None:
    user = SQLUserRepository(database_session_factory).create(_user())

    reloaded = SQLUserRepository(database_session_factory).get(user.id)

    assert reloaded == user
    assert reloaded is not user


def test_each_repository_operation_uses_a_fresh_session(
    database_session_factory: SessionFactory,
) -> None:
    sessions: list[Session] = []

    def counting_factory() -> Session:
        session = database_session_factory()
        sessions.append(session)
        return session

    repository = SQLUserRepository(counting_factory)
    user = repository.create(_user())
    repository.get(user.id)
    repository.get_by_username(user.username)

    assert len(sessions) == 3
    assert len({id(session) for session in sessions}) == 3


def test_real_user_service_hashes_and_persists_password(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLUserRepository(database_session_factory)
    service = UserService(
        repository,
        PasswordHasher(rounds=4),
        AccessTokenManager("test-secret", 30),
    )

    created = service.register(
        UserRegister(username="negotiator", password="secure-pass")
    )
    reloaded = SQLUserRepository(database_session_factory).get(created.id)

    assert reloaded is not None
    assert reloaded.password_hash != "secure-pass"
    assert PasswordHasher(rounds=4).verify("secure-pass", reloaded.password_hash)
