from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError
from tests.ownership import TEST_USER_ID


def _create_session() -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        user_id=TEST_USER_ID,
        scenario_id=uuid4(),
        status=NegotiationStatus.CREATED,
        created_at=now,
        updated_at=now,
    )


def test_create_stores_and_returns_session() -> None:
    repository = NegotiationRepository()
    session = _create_session()

    created = repository.create(session)

    assert created is session
    assert repository.get_for_user(session.id, TEST_USER_ID) is session


def test_get_returns_existing_session() -> None:
    repository = NegotiationRepository()
    session = repository.create(_create_session())

    assert repository.get_for_user(session.id, TEST_USER_ID) is session


def test_get_returns_none_for_missing_session() -> None:
    repository = NegotiationRepository()

    assert repository.get_for_user(uuid4(), TEST_USER_ID) is None


def test_list_returns_all_stored_sessions() -> None:
    repository = NegotiationRepository()
    first = repository.create(_create_session())
    second = repository.create(_create_session())

    assert repository.list_for_user(TEST_USER_ID) == [first, second]


def test_update_replaces_an_existing_session() -> None:
    repository = NegotiationRepository()
    session = repository.create(_create_session())
    session.status = NegotiationStatus.COMPLETED

    updated = repository.update_for_user(session, TEST_USER_ID)

    assert updated is session
    assert repository.get_for_user(session.id, TEST_USER_ID) is session


def test_update_rejects_a_missing_session() -> None:
    repository = NegotiationRepository()
    session = _create_session()

    with pytest.raises(NegotiationSessionNotFoundError) as exc_info:
        repository.update_for_user(session, TEST_USER_ID)

    assert exc_info.value.session_id == session.id
