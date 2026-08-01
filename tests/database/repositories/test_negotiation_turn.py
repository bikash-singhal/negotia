from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.negotiation_turn import (
    SQLNegotiationTurnRepository,
    negotiation_turn_to_domain,
    negotiation_turn_to_model,
)
from app.database.repositories.scenario import SQLScenarioRepository
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.schemas import NegotiationTurnCreate
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from tests.ownership import TEST_USER_ID

from .conftest import SessionFactory


def _scenario() -> Scenario:
    return Scenario(
        user_id=TEST_USER_ID,
        title="Software contract renewal",
        description="Renegotiate pricing and support for an enterprise subscription.",
        industry="Technology",
        opponent_role="Vendor account executive",
        objective="Improve support terms while controlling annual cost.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Prepared and analytical",
        negotiation_style="Collaborative",
    )


def _negotiation(scenario_id: UUID) -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        user_id=TEST_USER_ID,
        scenario_id=scenario_id,
        status=NegotiationStatus.CREATED,
        created_at=now,
        updated_at=now,
    )


def _turn(
    session_id: UUID,
    turn_number: int,
    *,
    turn_id: UUID | None = None,
    speaker: NegotiationTurnSpeaker = NegotiationTurnSpeaker.USER,
) -> NegotiationTurn:
    return NegotiationTurn(
        id=turn_id or uuid4(),
        session_id=session_id,
        speaker=speaker,
        content=f"Turn {turn_number} content",
        turn_number=turn_number,
        created_at=datetime.now(UTC),
    )


def _persist_negotiations(
    session_factory: SessionFactory,
    count: int = 1,
) -> tuple[SQLNegotiationRepository, list[NegotiationSession]]:
    scenario_repository = SQLScenarioRepository(session_factory)
    scenario = scenario_repository.create(_scenario())
    negotiation_repository = SQLNegotiationRepository(session_factory)
    negotiations = [
        negotiation_repository.create(_negotiation(scenario.scenario_id))
        for _ in range(count)
    ]
    return negotiation_repository, negotiations


def test_negotiation_turn_mapping_round_trip() -> None:
    turn = _turn(uuid4(), 1)

    assert negotiation_turn_to_domain(negotiation_turn_to_model(turn)) == turn


def test_create_and_get_persist_a_detached_domain_turn(
    database_session_factory: SessionFactory,
) -> None:
    _, negotiations = _persist_negotiations(database_session_factory)
    repository = SQLNegotiationTurnRepository(database_session_factory)
    turn = _turn(negotiations[0].id, 1)

    created = repository.create(turn, TEST_USER_ID)

    assert created == turn
    assert created is not turn
    assert repository.get_for_user(turn.id, TEST_USER_ID) == turn
    assert repository.get_for_user(uuid4(), TEST_USER_ID) is None


def test_list_by_session_orders_turns_by_turn_number(
    database_session_factory: SessionFactory,
) -> None:
    _, negotiations = _persist_negotiations(database_session_factory)
    repository = SQLNegotiationTurnRepository(database_session_factory)
    third = repository.create(_turn(negotiations[0].id, 3), TEST_USER_ID)
    first = repository.create(_turn(negotiations[0].id, 1), TEST_USER_ID)
    second = repository.create(_turn(negotiations[0].id, 2), TEST_USER_ID)

    assert repository.list_by_session_for_user(negotiations[0].id, TEST_USER_ID) == [
        first,
        second,
        third,
    ]


def test_list_by_session_does_not_mix_negotiations(
    database_session_factory: SessionFactory,
) -> None:
    _, negotiations = _persist_negotiations(database_session_factory, count=2)
    repository = SQLNegotiationTurnRepository(database_session_factory)
    first_turn = repository.create(_turn(negotiations[0].id, 1), TEST_USER_ID)
    second_turn = repository.create(_turn(negotiations[1].id, 1), TEST_USER_ID)

    assert repository.list_by_session_for_user(negotiations[0].id, TEST_USER_ID) == [
        first_turn
    ]
    assert repository.list_by_session_for_user(negotiations[1].id, TEST_USER_ID) == [
        second_turn
    ]
    assert repository.list_by_session_for_user(uuid4(), TEST_USER_ID) == []


def test_duplicate_turn_id_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    _, negotiations = _persist_negotiations(database_session_factory, count=2)
    repository = SQLNegotiationTurnRepository(database_session_factory)
    turn_id = uuid4()
    repository.create(_turn(negotiations[0].id, 1, turn_id=turn_id), TEST_USER_ID)

    with pytest.raises(IntegrityError):
        repository.create(_turn(negotiations[1].id, 1, turn_id=turn_id), TEST_USER_ID)


def test_duplicate_session_turn_number_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    _, negotiations = _persist_negotiations(database_session_factory)
    repository = SQLNegotiationTurnRepository(database_session_factory)
    repository.create(_turn(negotiations[0].id, 1), TEST_USER_ID)

    with pytest.raises(IntegrityError):
        repository.create(_turn(negotiations[0].id, 1), TEST_USER_ID)


def test_missing_negotiation_foreign_key_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLNegotiationTurnRepository(database_session_factory)

    with pytest.raises(NegotiationSessionNotFoundError):
        repository.create(_turn(uuid4(), 1), TEST_USER_ID)

    assert repository.list_by_session_for_user(uuid4(), TEST_USER_ID) == []


def test_rollback_preserves_previously_persisted_turns(
    database_session_factory: SessionFactory,
) -> None:
    _, negotiations = _persist_negotiations(database_session_factory)
    repository = SQLNegotiationTurnRepository(database_session_factory)
    original = repository.create(_turn(negotiations[0].id, 1), TEST_USER_ID)

    with pytest.raises(IntegrityError):
        repository.create(_turn(negotiations[0].id, 1), TEST_USER_ID)

    assert repository.list_by_session_for_user(negotiations[0].id, TEST_USER_ID) == [
        original
    ]


def test_each_operation_uses_a_fresh_sqlalchemy_session(
    database_session_factory: SessionFactory,
) -> None:
    _, negotiations = _persist_negotiations(database_session_factory)
    opened_sessions: list[Session] = []

    def tracking_session_factory() -> Session:
        database_session = database_session_factory()
        opened_sessions.append(database_session)
        return database_session

    repository = SQLNegotiationTurnRepository(tracking_session_factory)
    turn = repository.create(_turn(negotiations[0].id, 1), TEST_USER_ID)
    repository.get_for_user(turn.id, TEST_USER_ID)
    repository.list_by_session_for_user(negotiations[0].id, TEST_USER_ID)

    assert len(opened_sessions) == 3
    assert len({id(database_session) for database_session in opened_sessions}) == 3


def test_negotiation_turn_service_behavior_is_unchanged(
    database_session_factory: SessionFactory,
) -> None:
    negotiation_repository, negotiations = _persist_negotiations(
        database_session_factory
    )
    turn_repository = SQLNegotiationTurnRepository(database_session_factory)
    service = NegotiationTurnService(turn_repository, negotiation_repository)

    first = service.create_turn(
        NegotiationTurnCreate(
            session_id=negotiations[0].id,
            speaker=NegotiationTurnSpeaker.USER,
            content="Our target is a ten percent reduction.",
        ),
        TEST_USER_ID,
    )
    second = service.create_turn(
        NegotiationTurnCreate(
            session_id=negotiations[0].id,
            speaker=NegotiationTurnSpeaker.OPPONENT,
            content="We can discuss a smaller adjustment.",
        ),
        TEST_USER_ID,
    )

    assert first.turn_number == 1
    assert second.turn_number == 2
    assert service.get_turn(first.id, TEST_USER_ID) == first
    assert service.list_turns(negotiations[0].id, TEST_USER_ID) == [first, second]
