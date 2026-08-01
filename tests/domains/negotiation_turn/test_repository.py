from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from tests.ownership import TEST_USER_ID


def _create_turn(
    *,
    session_id: UUID | None = None,
    turn_number: int = 1,
) -> NegotiationTurn:
    return NegotiationTurn(
        id=uuid4(),
        session_id=session_id or uuid4(),
        speaker=NegotiationTurnSpeaker.USER,
        content="I would like to discuss the contract terms.",
        turn_number=turn_number,
        created_at=datetime.now(UTC),
    )


def test_create_stores_and_get_returns_turn() -> None:
    repository = NegotiationTurnRepository()
    turn = _create_turn()

    created = repository.create(turn, TEST_USER_ID)

    assert created is turn
    assert repository.get_for_user(turn.id, TEST_USER_ID) is turn


def test_get_returns_none_for_missing_turn() -> None:
    repository = NegotiationTurnRepository()

    assert repository.get_for_user(uuid4(), TEST_USER_ID) is None


def test_list_by_session_returns_empty_list() -> None:
    repository = NegotiationTurnRepository()

    assert repository.list_by_session_for_user(uuid4(), TEST_USER_ID) == []


def test_list_by_session_returns_only_requested_session_turns() -> None:
    repository = NegotiationTurnRepository()
    session_id = uuid4()
    first = repository.create(_create_turn(session_id=session_id), TEST_USER_ID)
    second = repository.create(
        _create_turn(session_id=session_id, turn_number=2), TEST_USER_ID
    )
    repository.create(_create_turn(), TEST_USER_ID)

    assert repository.list_by_session_for_user(session_id, TEST_USER_ID) == [
        first,
        second,
    ]


def test_list_by_session_orders_turns_by_turn_number() -> None:
    repository = NegotiationTurnRepository()
    session_id = uuid4()
    third = repository.create(
        _create_turn(session_id=session_id, turn_number=3), TEST_USER_ID
    )
    first = repository.create(_create_turn(session_id=session_id), TEST_USER_ID)
    second = repository.create(
        _create_turn(session_id=session_id, turn_number=2), TEST_USER_ID
    )

    assert repository.list_by_session_for_user(session_id, TEST_USER_ID) == [
        first,
        second,
        third,
    ]
