from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.repositories.memory import (
    SQLNegotiatorMemoryRepository,
    negotiator_memory_sources_to_models,
    negotiator_memory_to_domain,
    negotiator_memory_to_model,
)
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.scenario import SQLScenarioRepository
from app.domains.debrief.models import NegotiationDebrief, NegotiationDebriefRecord
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.memory.exceptions import NegotiatorMemoryAlreadyExistsError
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
)
from app.domains.strategy.repository import NegotiationStrategyRepository
from app.services.memory import MemoryExtractor, MemoryService

from .conftest import SessionFactory


def _scenario() -> Scenario:
    return Scenario(
        title="Supplier contract renewal",
        description="Negotiate pricing and delivery commitments with a supplier.",
        industry="Manufacturing",
        opponent_role="Supplier account director",
        objective="Secure reliable delivery while protecting commercial value.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Analytical and composed",
        negotiation_style="Collaborative but firm",
    )


def _persist_sessions(
    session_factory: SessionFactory,
    *,
    count: int = 2,
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
                    status=NegotiationStatus.COMPLETED,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
        )
    return sessions


def _memory(sessions_analyzed: int = 2) -> NegotiatorMemory:
    return NegotiatorMemory(
        recurring_strengths=["Uses conditional concessions."],
        recurring_weaknesses=["Anchors before discovery."],
        improving_skills=["Diagnostic questioning"],
        persistent_risks=["Concedes without reciprocal value."],
        priority_focus_areas=["Concession planning"],
        recommended_drills=["Prepare reciprocal asks."],
        sessions_analyzed=sessions_analyzed,
        confidence="high",
    )


def _record(
    source_session_ids: tuple[UUID, ...],
    *,
    record_id: UUID | None = None,
    trigger_session_id: UUID | None = None,
    created_at: datetime | None = None,
) -> NegotiatorMemoryRecord:
    return NegotiatorMemoryRecord(
        id=record_id or uuid4(),
        trigger_session_id=trigger_session_id,
        memory=_memory(len(source_session_ids)),
        source_session_ids=source_session_ids,
        created_at=created_at or datetime.now(UTC),
    )


def _debrief_record(session_id: UUID) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=NegotiationDebrief(
            repeated_strengths=["Used conditional concessions."],
            repeated_weaknesses=["Anchored before discovery."],
            key_missed_opportunities=["Did not test the deadline."],
            recurring_risks=["Made unilateral concessions."],
            overall_assessment="Constructive but too quick to concede.",
            confidence="high",
        ),
        observation_count=2,
        created_at=datetime.now(UTC),
    )


def _strategy_record(
    session_id: UUID,
    debrief_id: UUID,
) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=debrief_id,
        strategy=NegotiationStrategy(
            primary_objective="Make every concession conditional.",
            expected_outcome="Receive reciprocal value for concessions.",
            prioritized_tactics=[],
            long_term_skills=["Concession planning"],
            preparation_checklist=["Define reciprocal asks."],
            avoid_next_time=["Avoid unilateral concessions."],
            confidence="high",
        ),
        created_at=datetime.now(UTC),
    )


def test_negotiator_memory_mapping_round_trip_copies_all_lists() -> None:
    source_session_ids = (uuid4(), uuid4())
    record = _record(source_session_ids)
    model = negotiator_memory_to_model(record)
    source_models = negotiator_memory_sources_to_models(record)

    mapped = negotiator_memory_to_domain(model, list(reversed(source_models)))

    assert mapped == record
    assert model.recurring_strengths is not record.memory.recurring_strengths
    assert model.recurring_weaknesses is not record.memory.recurring_weaknesses
    assert model.improving_skills is not record.memory.improving_skills
    assert model.persistent_risks is not record.memory.persistent_risks
    assert model.priority_focus_areas is not record.memory.priority_focus_areas
    assert model.recommended_drills is not record.memory.recommended_drills
    assert mapped.memory.recurring_strengths is not model.recurring_strengths
    assert mapped.memory.recurring_weaknesses is not model.recurring_weaknesses
    assert mapped.memory.improving_skills is not model.improving_skills
    assert mapped.memory.persistent_risks is not model.persistent_risks
    assert mapped.memory.priority_focus_areas is not model.priority_focus_areas
    assert mapped.memory.recommended_drills is not model.recommended_drills


def test_create_reads_and_list_return_detached_persisted_records(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory)
    repository = SQLNegotiatorMemoryRepository(database_session_factory)
    record = _record(
        (sessions[1].id, sessions[0].id),
        trigger_session_id=sessions[1].id,
    )

    created = repository.create(record)
    fresh_repository = SQLNegotiatorMemoryRepository(database_session_factory)
    reloaded = fresh_repository.get_by_trigger_session(sessions[1].id)

    assert created == record
    assert created is not record
    assert created.memory is not record.memory
    assert reloaded == record
    assert fresh_repository.get_by_trigger_session(uuid4()) is None
    assert fresh_repository.get_latest() == record
    assert fresh_repository.list_all() == [record]


def test_trigger_lookup_is_isolated_and_versions_are_chronological(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory)
    repository = SQLNegotiatorMemoryRepository(database_session_factory)
    now = datetime.now(UTC)
    first = repository.create(
        _record(
            (sessions[0].id, sessions[1].id),
            trigger_session_id=sessions[0].id,
            created_at=now,
        )
    )
    second = repository.create(
        _record(
            (sessions[0].id, sessions[1].id),
            trigger_session_id=sessions[1].id,
            created_at=now + timedelta(seconds=1),
        )
    )

    assert repository.get_by_trigger_session(sessions[0].id) == first
    assert repository.get_by_trigger_session(sessions[1].id) == second
    assert repository.list_all() == [first, second]
    assert repository.get_latest() == second


def test_multiple_standalone_versions_are_allowed_and_not_trigger_records(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory)
    repository = SQLNegotiatorMemoryRepository(database_session_factory)
    sources = (sessions[0].id, sessions[1].id)

    first = repository.create(_record(sources))
    second = repository.create(_record(sources))

    assert repository.list_all() == [first, second]
    assert repository.get_by_trigger_session(sessions[0].id) is None


def test_duplicate_trigger_preserves_domain_exception_behavior(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory)
    repository = SQLNegotiatorMemoryRepository(database_session_factory)
    sources = (sessions[0].id, sessions[1].id)
    original = repository.create(_record(sources, trigger_session_id=sessions[0].id))

    with pytest.raises(NegotiatorMemoryAlreadyExistsError) as exc_info:
        repository.create(_record(sources, trigger_session_id=sessions[0].id))

    assert exc_info.value.trigger_session_id == sessions[0].id
    assert repository.get_by_trigger_session(sessions[0].id) == original


def test_duplicate_primary_key_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory)
    repository = SQLNegotiatorMemoryRepository(database_session_factory)
    sources = (sessions[0].id, sessions[1].id)
    record_id = uuid4()
    repository.create(_record(sources, record_id=record_id))

    with pytest.raises(IntegrityError):
        repository.create(_record(sources, record_id=record_id))


def test_missing_trigger_session_foreign_key_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory)
    repository = SQLNegotiatorMemoryRepository(database_session_factory)

    with pytest.raises(IntegrityError):
        repository.create(
            _record(
                (sessions[0].id, sessions[1].id),
                trigger_session_id=uuid4(),
            )
        )


def test_missing_source_session_foreign_key_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    session = _persist_sessions(database_session_factory, count=1)[0]
    repository = SQLNegotiatorMemoryRepository(database_session_factory)

    with pytest.raises(IntegrityError):
        repository.create(_record((session.id, uuid4())))


def test_rollback_preserves_previously_persisted_memory(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory)
    repository = SQLNegotiatorMemoryRepository(database_session_factory)
    original = repository.create(_record((sessions[0].id, sessions[1].id)))

    with pytest.raises(IntegrityError):
        repository.create(_record((sessions[0].id, uuid4())))

    assert repository.list_all() == [original]
    assert repository.get_latest() == original


def test_each_operation_uses_a_fresh_sqlalchemy_session(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory)
    opened_sessions: list[Session] = []

    def tracking_session_factory() -> Session:
        database_session = database_session_factory()
        opened_sessions.append(database_session)
        return database_session

    repository = SQLNegotiatorMemoryRepository(tracking_session_factory)
    record = repository.create(
        _record(
            (sessions[0].id, sessions[1].id),
            trigger_session_id=sessions[0].id,
        )
    )
    repository.get_latest()
    repository.list_all()
    repository.get_by_trigger_session(record.trigger_session_id or uuid4())

    assert len(opened_sessions) == 4
    assert len({id(database_session) for database_session in opened_sessions}) == 4


def test_memory_service_behavior_is_unchanged_and_persisted(
    database_session_factory: SessionFactory,
) -> None:
    sessions = _persist_sessions(database_session_factory)
    debrief_repository = NegotiationDebriefRepository()
    strategy_repository = NegotiationStrategyRepository()
    for session in sessions:
        debrief = debrief_repository.create(_debrief_record(session.id))
        strategy_repository.create(_strategy_record(session.id, debrief.id))

    extractor = MagicMock(spec=MemoryExtractor)
    extractor.extract.return_value = _memory()
    repository = SQLNegotiatorMemoryRepository(database_session_factory)
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        repository,
    )

    result = service.generate_for_session(sessions[1].id)

    assert result is not None
    reloaded = SQLNegotiatorMemoryRepository(
        database_session_factory
    ).get_by_trigger_session(sessions[1].id)
    repeated = service.generate_for_session(sessions[1].id)
    assert reloaded == result
    assert repeated == result
    assert result.source_session_ids == tuple(sorted((s.id for s in sessions), key=str))
    extractor.extract.assert_called_once()
