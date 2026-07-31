from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.repositories.coach import SQLCoachObservationRepository
from app.database.repositories.debrief import (
    SQLNegotiationDebriefRepository,
    negotiation_debrief_to_domain,
    negotiation_debrief_to_model,
)
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.negotiation_turn import SQLNegotiationTurnRepository
from app.database.repositories.scenario import SQLScenarioRepository
from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.debrief.exceptions import NegotiationDebriefAlreadyExistsError
from app.domains.debrief.models import NegotiationDebrief, NegotiationDebriefRecord
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.services.debrief import DebriefExtractor, DebriefService

from .conftest import SessionFactory


def _scenario() -> Scenario:
    return Scenario(
        title="Consulting agreement",
        description="Negotiate scope, fees, and delivery terms for an engagement.",
        industry="Professional services",
        opponent_role="Client procurement manager",
        objective="Protect fees while clarifying delivery responsibilities.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Detail-oriented and pragmatic",
        negotiation_style="Collaborative",
    )


def _persist_sessions(
    session_factory: SessionFactory,
    *,
    count: int = 1,
) -> list[NegotiationSession]:
    scenario = SQLScenarioRepository(session_factory).create(_scenario())
    repository = SQLNegotiationRepository(session_factory)
    sessions: list[NegotiationSession] = []
    for offset in range(count):
        created_at = datetime.now(UTC) + timedelta(seconds=offset)
        sessions.append(
            repository.create(
                NegotiationSession(
                    id=uuid4(),
                    scenario_id=scenario.scenario_id,
                    status=NegotiationStatus.CREATED,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
        )
    return sessions


def _debrief() -> NegotiationDebrief:
    return NegotiationDebrief(
        repeated_strengths=["Used conditional concessions."],
        repeated_weaknesses=["Anchored before gathering enough information."],
        key_missed_opportunities=["Did not test the delivery deadline."],
        recurring_risks=["Conceded without receiving reciprocal value."],
        overall_assessment="The user negotiated constructively but conceded early.",
        confidence="high",
    )


def _record(
    session_id: UUID,
    *,
    record_id: UUID | None = None,
    observation_count: int = 2,
) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=record_id or uuid4(),
        session_id=session_id,
        debrief=_debrief(),
        observation_count=observation_count,
        created_at=datetime.now(UTC),
    )


def test_negotiation_debrief_mapping_round_trip_copies_lists() -> None:
    record = _record(uuid4())

    mapped = negotiation_debrief_to_domain(negotiation_debrief_to_model(record))

    assert mapped == record
    assert mapped.debrief.repeated_strengths is not record.debrief.repeated_strengths
    assert mapped.debrief.repeated_weaknesses is not record.debrief.repeated_weaknesses
    assert mapped.debrief.key_missed_opportunities is not (
        record.debrief.key_missed_opportunities
    )
    assert mapped.debrief.recurring_risks is not record.debrief.recurring_risks


def test_create_and_get_by_session_return_detached_domain_record(
    database_session_factory: SessionFactory,
) -> None:
    session = _persist_sessions(database_session_factory)[0]
    repository = SQLNegotiationDebriefRepository(database_session_factory)
    record = _record(session.id)

    created = repository.create(record)
    reloaded = SQLNegotiationDebriefRepository(database_session_factory).get_by_session(
        session.id
    )

    assert created == record
    assert created is not record
    assert created.debrief is not record.debrief
    assert reloaded == record
    assert repository.get_by_session(uuid4()) is None


def test_get_by_session_keeps_sessions_isolated(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory, count=2)
    repository = SQLNegotiationDebriefRepository(database_session_factory)
    first = repository.create(_record(sessions[0].id))
    second = repository.create(_record(sessions[1].id))

    assert repository.get_by_session(sessions[0].id) == first
    assert repository.get_by_session(sessions[1].id) == second


def test_duplicate_session_preserves_domain_exception_behavior(
    database_session_factory: SessionFactory,
) -> None:
    session = _persist_sessions(database_session_factory)[0]
    repository = SQLNegotiationDebriefRepository(database_session_factory)
    original = repository.create(_record(session.id))

    with pytest.raises(NegotiationDebriefAlreadyExistsError) as exc_info:
        repository.create(_record(session.id))

    assert exc_info.value.session_id == session.id
    assert repository.get_by_session(session.id) == original


def test_duplicate_primary_key_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory, count=2)
    repository = SQLNegotiationDebriefRepository(database_session_factory)
    record_id = uuid4()
    repository.create(_record(sessions[0].id, record_id=record_id))

    with pytest.raises(IntegrityError):
        repository.create(_record(sessions[1].id, record_id=record_id))


def test_missing_negotiation_foreign_key_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLNegotiationDebriefRepository(database_session_factory)

    with pytest.raises(IntegrityError):
        repository.create(_record(uuid4()))


def test_rollback_preserves_previously_persisted_debrief(
    database_session_factory: SessionFactory,
) -> None:
    session = _persist_sessions(database_session_factory)[0]
    repository = SQLNegotiationDebriefRepository(database_session_factory)
    original = repository.create(_record(session.id))

    with pytest.raises(IntegrityError):
        repository.create(_record(uuid4()))

    assert repository.get_by_session(session.id) == original


def test_each_operation_uses_a_fresh_sqlalchemy_session(
    database_session_factory: SessionFactory,
) -> None:
    session = _persist_sessions(database_session_factory)[0]
    opened_sessions: list[Session] = []

    def tracking_session_factory() -> Session:
        database_session = database_session_factory()
        opened_sessions.append(database_session)
        return database_session

    repository = SQLNegotiationDebriefRepository(tracking_session_factory)
    repository.create(_record(session.id))
    repository.get_by_session(session.id)

    assert len(opened_sessions) == 2
    assert len({id(database_session) for database_session in opened_sessions}) == 2


def test_debrief_service_behavior_is_unchanged_and_persisted(
    database_session_factory: SessionFactory,
) -> None:
    session = _persist_sessions(database_session_factory)[0]
    now = datetime.now(UTC)
    turn_repository = SQLNegotiationTurnRepository(database_session_factory)
    user_turn = turn_repository.create(
        NegotiationTurn(
            id=uuid4(),
            session_id=session.id,
            speaker=NegotiationTurnSpeaker.USER,
            content="We need a ten percent fee reduction.",
            turn_number=1,
            created_at=now,
        )
    )
    opponent_turn = turn_repository.create(
        NegotiationTurn(
            id=uuid4(),
            session_id=session.id,
            speaker=NegotiationTurnSpeaker.OPPONENT,
            content="We can discuss scope changes instead.",
            turn_number=2,
            created_at=now + timedelta(seconds=1),
        )
    )
    coach_repository = SQLCoachObservationRepository(database_session_factory)
    observation = coach_repository.create(
        CoachObservationRecord(
            id=uuid4(),
            session_id=session.id,
            user_turn_id=user_turn.id,
            opponent_turn_id=opponent_turn.id,
            observation=CoachObservation(
                strengths=["Protected the core objective."],
                weaknesses=[],
                missed_opportunities=[],
                risk_signals=[],
                confidence="high",
            ),
            created_at=now + timedelta(seconds=2),
        )
    )
    extractor = MagicMock(spec=DebriefExtractor)
    extractor.extract.return_value = _debrief()
    repository = SQLNegotiationDebriefRepository(database_session_factory)
    service = DebriefService(coach_repository, extractor, repository)

    result = service.generate_for_session(session.id)
    reloaded = SQLNegotiationDebriefRepository(database_session_factory).get_by_session(
        session.id
    )

    assert result.debrief == _debrief()
    assert result.observation_count == 1
    assert reloaded == result
    assert service.get_for_session(session.id) == result
    extractor.extract.assert_called_once_with([observation])
