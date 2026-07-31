from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.repositories.coach import (
    SQLCoachObservationRepository,
    coach_observation_to_domain,
    coach_observation_to_model,
)
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.negotiation_turn import SQLNegotiationTurnRepository
from app.database.repositories.scenario import SQLScenarioRepository
from app.domains.coach.exceptions import CoachObservationAlreadyExistsError
from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.services.adaptive_context import AdaptiveContextService
from app.services.coach import CoachObservationExtractor, CoachService

from .conftest import SessionFactory


def _scenario() -> Scenario:
    return Scenario(
        title="Distribution agreement",
        description="Negotiate pricing and territory for a distribution agreement.",
        industry="Consumer goods",
        opponent_role="Distribution director",
        objective="Secure broad territory with sustainable pricing.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Commercial and methodical",
        negotiation_style="Collaborative",
    )


def _persist_exchange(
    session_factory: SessionFactory,
    *,
    turn_count: int = 2,
) -> tuple[NegotiationSession, list[NegotiationTurn]]:
    scenario = SQLScenarioRepository(session_factory).create(_scenario())
    now = datetime.now(UTC)
    negotiation = SQLNegotiationRepository(session_factory).create(
        NegotiationSession(
            id=uuid4(),
            scenario_id=scenario.scenario_id,
            status=NegotiationStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
    )
    turn_repository = SQLNegotiationTurnRepository(session_factory)
    turns = [
        turn_repository.create(
            NegotiationTurn(
                id=uuid4(),
                session_id=negotiation.id,
                speaker=(
                    NegotiationTurnSpeaker.USER
                    if turn_number % 2 == 1
                    else NegotiationTurnSpeaker.OPPONENT
                ),
                content=f"Turn {turn_number} content",
                turn_number=turn_number,
                created_at=now + timedelta(seconds=turn_number),
            )
        )
        for turn_number in range(1, turn_count + 1)
    ]
    return negotiation, turns


def _record(
    session_id: UUID,
    user_turn_id: UUID,
    opponent_turn_id: UUID,
    *,
    record_id: UUID | None = None,
    created_at: datetime | None = None,
) -> CoachObservationRecord:
    return CoachObservationRecord(
        id=record_id or uuid4(),
        session_id=session_id,
        user_turn_id=user_turn_id,
        opponent_turn_id=opponent_turn_id,
        observation=CoachObservation(
            strengths=["Made a conditional proposal."],
            weaknesses=["Did not confirm the counterparty's priority."],
            missed_opportunities=["Could have tested the delivery constraint."],
            risk_signals=["Conceded before receiving reciprocal value."],
            confidence="high",
        ),
        created_at=created_at or datetime.now(UTC),
    )


def test_coach_observation_mapping_round_trip_copies_lists() -> None:
    record = _record(uuid4(), uuid4(), uuid4())

    mapped = coach_observation_to_domain(coach_observation_to_model(record))

    assert mapped == record
    assert mapped.observation.strengths is not record.observation.strengths
    assert mapped.observation.weaknesses is not record.observation.weaknesses
    assert mapped.observation.missed_opportunities is not (
        record.observation.missed_opportunities
    )
    assert mapped.observation.risk_signals is not record.observation.risk_signals


def test_create_and_list_persist_detached_domain_records(
    database_session_factory: SessionFactory,
) -> None:
    negotiation, turns = _persist_exchange(database_session_factory)
    repository = SQLCoachObservationRepository(database_session_factory)
    record = _record(negotiation.id, turns[0].id, turns[1].id)

    created = repository.create(record)

    assert created == record
    assert created is not record
    assert created.observation is not record.observation
    assert repository.list_by_session(negotiation.id) == [record]
    assert repository.list_by_session(uuid4()) == []


def test_list_by_session_preserves_chronological_creation_order(
    database_session_factory: SessionFactory,
) -> None:
    negotiation, turns = _persist_exchange(
        database_session_factory,
        turn_count=4,
    )
    repository = SQLCoachObservationRepository(database_session_factory)
    now = datetime.now(UTC)
    first = repository.create(
        _record(
            negotiation.id,
            turns[0].id,
            turns[1].id,
            created_at=now,
        )
    )
    second = repository.create(
        _record(
            negotiation.id,
            turns[2].id,
            turns[3].id,
            created_at=now + timedelta(seconds=1),
        )
    )

    assert repository.list_by_session(negotiation.id) == [first, second]


def test_duplicate_exchange_preserves_domain_exception_behavior(
    database_session_factory: SessionFactory,
) -> None:
    negotiation, turns = _persist_exchange(database_session_factory)
    repository = SQLCoachObservationRepository(database_session_factory)
    original = repository.create(_record(negotiation.id, turns[0].id, turns[1].id))

    with pytest.raises(CoachObservationAlreadyExistsError) as exc_info:
        repository.create(_record(negotiation.id, turns[0].id, turns[1].id))

    assert exc_info.value.user_turn_id == turns[0].id
    assert exc_info.value.opponent_turn_id == turns[1].id
    assert repository.list_by_session(negotiation.id) == [original]


def test_duplicate_record_id_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    negotiation, turns = _persist_exchange(
        database_session_factory,
        turn_count=4,
    )
    repository = SQLCoachObservationRepository(database_session_factory)
    record_id = uuid4()
    repository.create(
        _record(
            negotiation.id,
            turns[0].id,
            turns[1].id,
            record_id=record_id,
        )
    )

    with pytest.raises(IntegrityError):
        repository.create(
            _record(
                negotiation.id,
                turns[2].id,
                turns[3].id,
                record_id=record_id,
            )
        )


def test_missing_foreign_keys_raise_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLCoachObservationRepository(database_session_factory)

    with pytest.raises(IntegrityError):
        repository.create(_record(uuid4(), uuid4(), uuid4()))


def test_rollback_preserves_previously_persisted_records(
    database_session_factory: SessionFactory,
) -> None:
    negotiation, turns = _persist_exchange(database_session_factory)
    repository = SQLCoachObservationRepository(database_session_factory)
    original = repository.create(_record(negotiation.id, turns[0].id, turns[1].id))

    with pytest.raises(IntegrityError):
        repository.create(_record(uuid4(), uuid4(), uuid4()))

    assert repository.list_by_session(negotiation.id) == [original]


def test_each_operation_uses_a_fresh_sqlalchemy_session(
    database_session_factory: SessionFactory,
) -> None:
    negotiation, turns = _persist_exchange(database_session_factory)
    opened_sessions: list[Session] = []

    def tracking_session_factory() -> Session:
        database_session = database_session_factory()
        opened_sessions.append(database_session)
        return database_session

    repository = SQLCoachObservationRepository(tracking_session_factory)
    repository.create(_record(negotiation.id, turns[0].id, turns[1].id))
    repository.list_by_session(negotiation.id)

    assert len(opened_sessions) == 2
    assert len({id(database_session) for database_session in opened_sessions}) == 2


def test_coach_service_behavior_is_unchanged(
    database_session_factory: SessionFactory,
) -> None:
    negotiation, turns = _persist_exchange(database_session_factory)
    repository = SQLCoachObservationRepository(database_session_factory)
    observation = CoachObservation(
        strengths=["Protected the core objective."],
        weaknesses=[],
        missed_opportunities=[],
        risk_signals=[],
        confidence="high",
    )
    extractor = MagicMock(spec=CoachObservationExtractor)
    extractor.extract.return_value = observation
    adaptive_context_service = MagicMock(spec=AdaptiveContextService)
    adaptive_context_service.get_context.return_value = None
    service = CoachService(extractor, repository, adaptive_context_service)

    result = service.analyze_exchange(
        negotiation.id,
        turns,
        turns[0],
        turns[1],
    )

    assert result.observation == observation
    assert repository.list_by_session(negotiation.id) == [result]
    extractor.extract.assert_called_once_with(turns, None)
