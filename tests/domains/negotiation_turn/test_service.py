from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.negotiation.models import (
    NegotiationSession,
    NegotiationStatus,
)
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation_turn.exceptions import (
    NegotiationSessionNotFoundError,
)
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.negotiation_turn.schemas import NegotiationTurnCreate
from app.domains.negotiation_turn.service import NegotiationTurnService


def _create_session(session_id: UUID | None = None) -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=session_id or uuid4(),
        scenario_id=uuid4(),
        status=NegotiationStatus.CREATED,
        created_at=now,
        updated_at=now,
    )


def _create_request(session_id: UUID) -> NegotiationTurnCreate:
    return NegotiationTurnCreate(
        session_id=session_id,
        speaker=NegotiationTurnSpeaker.USER,
        content="I would like to discuss the contract terms.",
    )


def _create_turn(session_id: UUID | None = None) -> NegotiationTurn:
    return NegotiationTurn(
        id=uuid4(),
        session_id=session_id or uuid4(),
        speaker=NegotiationTurnSpeaker.USER,
        content="I would like to discuss the contract terms.",
        turn_number=1,
        created_at=datetime.now(UTC),
    )


def test_create_turn_generates_uuid_and_utc_timestamp() -> None:
    negotiation_repository = NegotiationRepository()
    session = negotiation_repository.create(_create_session())
    service = NegotiationTurnService(
        NegotiationTurnRepository(),
        negotiation_repository,
    )

    turn = service.create_turn(_create_request(session.id))

    assert isinstance(turn.id, UUID)
    assert turn.created_at.tzinfo is not None
    assert turn.created_at.utcoffset() == timedelta(0)


def test_create_turn_maps_request_fields() -> None:
    negotiation_repository = NegotiationRepository()
    session = negotiation_repository.create(_create_session())
    service = NegotiationTurnService(
        NegotiationTurnRepository(),
        negotiation_repository,
    )
    request = _create_request(session.id)

    turn = service.create_turn(request)

    assert turn.session_id == request.session_id
    assert turn.speaker is request.speaker
    assert turn.content == request.content


def test_first_turn_has_turn_number_one() -> None:
    negotiation_repository = NegotiationRepository()
    session = negotiation_repository.create(_create_session())
    service = NegotiationTurnService(
        NegotiationTurnRepository(),
        negotiation_repository,
    )

    turn = service.create_turn(_create_request(session.id))

    assert turn.turn_number == 1


def test_subsequent_turn_numbers_increment() -> None:
    negotiation_repository = NegotiationRepository()
    session = negotiation_repository.create(_create_session())
    service = NegotiationTurnService(
        NegotiationTurnRepository(),
        negotiation_repository,
    )

    first = service.create_turn(_create_request(session.id))
    second = service.create_turn(_create_request(session.id))

    assert first.turn_number == 1
    assert second.turn_number == 2


def test_turn_numbering_is_independent_for_each_session() -> None:
    negotiation_repository = NegotiationRepository()
    first_session = negotiation_repository.create(_create_session())
    second_session = negotiation_repository.create(_create_session())
    service = NegotiationTurnService(
        NegotiationTurnRepository(),
        negotiation_repository,
    )

    first_turn = service.create_turn(_create_request(first_session.id))
    second_turn = service.create_turn(_create_request(first_session.id))
    other_session_turn = service.create_turn(_create_request(second_session.id))

    assert first_turn.turn_number == 1
    assert second_turn.turn_number == 2
    assert other_session_turn.turn_number == 1


def test_missing_session_raises_domain_exception() -> None:
    session_id = uuid4()
    turn_repository = MagicMock(spec=NegotiationTurnRepository)
    negotiation_repository = MagicMock(spec=NegotiationRepository)
    negotiation_repository.get.return_value = None
    service = NegotiationTurnService(
        turn_repository,
        negotiation_repository,
    )

    with pytest.raises(NegotiationSessionNotFoundError) as exc_info:
        service.create_turn(_create_request(session_id))

    assert exc_info.value.session_id == session_id
    assert str(exc_info.value) == (
        f"Negotiation session with id '{session_id}' was not found."
    )
    negotiation_repository.get.assert_called_once_with(session_id)
    turn_repository.list_by_session.assert_not_called()
    turn_repository.create.assert_not_called()


def test_create_turn_passes_turn_to_repository() -> None:
    session = _create_session()
    turn_repository = MagicMock(spec=NegotiationTurnRepository)
    turn_repository.list_by_session.return_value = []
    turn_repository.create.side_effect = lambda turn: turn
    negotiation_repository = MagicMock(spec=NegotiationRepository)
    negotiation_repository.get.return_value = session
    service = NegotiationTurnService(
        turn_repository,
        negotiation_repository,
    )

    turn = service.create_turn(_create_request(session.id))

    turn_repository.create.assert_called_once_with(turn)


def test_get_turn_delegates_to_repository() -> None:
    turn_repository = MagicMock(spec=NegotiationTurnRepository)
    negotiation_repository = MagicMock(spec=NegotiationRepository)
    service = NegotiationTurnService(
        turn_repository,
        negotiation_repository,
    )
    turn = _create_turn()
    turn_repository.get.return_value = turn

    result = service.get_turn(turn.id)

    assert result is turn
    turn_repository.get.assert_called_once_with(turn.id)


def test_list_turns_delegates_to_repository() -> None:
    turn_repository = MagicMock(spec=NegotiationTurnRepository)
    negotiation_repository = MagicMock(spec=NegotiationRepository)
    service = NegotiationTurnService(
        turn_repository,
        negotiation_repository,
    )
    session_id = uuid4()
    turns = [_create_turn(session_id), _create_turn(session_id)]
    turn_repository.list_by_session.return_value = turns

    result = service.list_turns(session_id)

    assert result == turns
    turn_repository.list_by_session.assert_called_once_with(session_id)
