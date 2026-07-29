from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.repository import NegotiationTurnRepository


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

    created = repository.create(turn)

    assert created is turn
    assert repository.get(turn.id) is turn


def test_get_returns_none_for_missing_turn() -> None:
    repository = NegotiationTurnRepository()

    assert repository.get(uuid4()) is None


def test_list_by_session_returns_empty_list() -> None:
    repository = NegotiationTurnRepository()

    assert repository.list_by_session(uuid4()) == []


def test_list_by_session_returns_only_requested_session_turns() -> None:
    repository = NegotiationTurnRepository()
    session_id = uuid4()
    first = repository.create(_create_turn(session_id=session_id))
    second = repository.create(_create_turn(session_id=session_id, turn_number=2))
    repository.create(_create_turn())

    assert repository.list_by_session(session_id) == [first, second]


def test_list_by_session_orders_turns_by_turn_number() -> None:
    repository = NegotiationTurnRepository()
    session_id = uuid4()
    third = repository.create(_create_turn(session_id=session_id, turn_number=3))
    first = repository.create(_create_turn(session_id=session_id))
    second = repository.create(_create_turn(session_id=session_id, turn_number=2))

    assert repository.list_by_session(session_id) == [first, second, third]
