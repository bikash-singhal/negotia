from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.repositories.debrief import SQLNegotiationDebriefRepository
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.scenario import SQLScenarioRepository
from app.database.repositories.strategy import (
    SQLNegotiationStrategyRepository,
    negotiation_strategy_to_domain,
    negotiation_strategy_to_model,
)
from app.domains.debrief.models import NegotiationDebrief, NegotiationDebriefRecord
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.strategy.exceptions import NegotiationStrategyAlreadyExistsError
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
    NegotiationTactic,
)
from app.services.strategy import StrategyExtractor, StrategyService

from .conftest import SessionFactory


def _scenario() -> Scenario:
    return Scenario(
        title="Employment offer",
        description="Negotiate compensation and working terms for a new role.",
        industry="Technology",
        opponent_role="Hiring manager",
        objective="Improve total compensation and role flexibility.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Pragmatic and data-driven",
        negotiation_style="Collaborative",
    )


def _persist_artifacts(
    session_factory: SessionFactory,
    *,
    count: int = 1,
) -> list[tuple[NegotiationSession, NegotiationDebriefRecord]]:
    scenario = SQLScenarioRepository(session_factory).create(_scenario())
    negotiation_repository = SQLNegotiationRepository(session_factory)
    debrief_repository = SQLNegotiationDebriefRepository(session_factory)
    artifacts: list[tuple[NegotiationSession, NegotiationDebriefRecord]] = []
    for offset in range(count):
        created_at = datetime.now(UTC) + timedelta(seconds=offset)
        session = negotiation_repository.create(
            NegotiationSession(
                id=uuid4(),
                scenario_id=scenario.scenario_id,
                status=NegotiationStatus.CREATED,
                created_at=created_at,
                updated_at=created_at,
            )
        )
        debrief = debrief_repository.create(
            NegotiationDebriefRecord(
                id=uuid4(),
                session_id=session.id,
                debrief=NegotiationDebrief(
                    repeated_strengths=["Used conditional concessions."],
                    repeated_weaknesses=["Anchored before discovery."],
                    key_missed_opportunities=["Did not test the deadline."],
                    recurring_risks=["Conceded without reciprocal value."],
                    overall_assessment="Constructive but quick to concede.",
                    confidence="high",
                ),
                observation_count=2,
                created_at=created_at,
            )
        )
        artifacts.append((session, debrief))
    return artifacts


def _strategy() -> NegotiationStrategy:
    return NegotiationStrategy(
        primary_objective="Make every concession conditional.",
        expected_outcome="Receive reciprocal value for each concession.",
        prioritized_tactics=[
            NegotiationTactic(
                priority=1,
                title="Trade rather than concede",
                rationale="Conditional trades protect value.",
                actions=["Request reciprocal movement."],
                example_language=["I can agree if the payment terms improve."],
                success_indicator="Every concession receives something in return.",
            ),
            NegotiationTactic(
                priority=2,
                title="Diagnose before proposing",
                rationale="Discovery reveals tradable priorities.",
                actions=["Ask about timing and implementation constraints."],
                example_language=["Which part of the timeline is least flexible?"],
                success_indicator="At least two priorities are confirmed.",
            ),
        ],
        long_term_skills=["Concession planning"],
        preparation_checklist=["Define reciprocal asks."],
        avoid_next_time=["Avoid unilateral concessions."],
        confidence="high",
    )


def _record(
    session_id: UUID,
    debrief_id: UUID,
    *,
    record_id: UUID | None = None,
    created_at: datetime | None = None,
) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=record_id or uuid4(),
        session_id=session_id,
        debrief_id=debrief_id,
        strategy=_strategy(),
        created_at=created_at or datetime.now(UTC),
    )


def test_negotiation_strategy_mapping_round_trip_copies_nested_lists() -> None:
    record = _record(uuid4(), uuid4())

    mapped = negotiation_strategy_to_domain(negotiation_strategy_to_model(record))

    assert mapped == record
    assert mapped.strategy.prioritized_tactics is not (
        record.strategy.prioritized_tactics
    )
    assert (
        mapped.strategy.prioritized_tactics[0]
        is not (record.strategy.prioritized_tactics[0])
    )
    assert mapped.strategy.prioritized_tactics[0].actions is not (
        record.strategy.prioritized_tactics[0].actions
    )
    assert mapped.strategy.prioritized_tactics[0].example_language is not (
        record.strategy.prioritized_tactics[0].example_language
    )
    assert mapped.strategy.long_term_skills is not record.strategy.long_term_skills
    assert mapped.strategy.preparation_checklist is not (
        record.strategy.preparation_checklist
    )
    assert mapped.strategy.avoid_next_time is not record.strategy.avoid_next_time


def test_create_get_and_list_return_detached_persisted_records(
    database_session_factory: SessionFactory,
) -> None:
    session, debrief = _persist_artifacts(database_session_factory)[0]
    repository = SQLNegotiationStrategyRepository(database_session_factory)
    record = _record(session.id, debrief.id)

    created = repository.create(record)
    reloaded = SQLNegotiationStrategyRepository(
        database_session_factory
    ).get_by_session(session.id)

    assert created == record
    assert created is not record
    assert created.strategy is not record.strategy
    assert reloaded == record
    assert repository.get_by_session(uuid4()) is None
    assert repository.list_all() == [record]


def test_get_by_session_keeps_sessions_isolated_and_list_is_chronological(
    database_session_factory: SessionFactory,
) -> None:
    artifacts = _persist_artifacts(database_session_factory, count=2)
    repository = SQLNegotiationStrategyRepository(database_session_factory)
    now = datetime.now(UTC)
    first = repository.create(
        _record(
            artifacts[0][0].id,
            artifacts[0][1].id,
            created_at=now,
        )
    )
    second = repository.create(
        _record(
            artifacts[1][0].id,
            artifacts[1][1].id,
            created_at=now + timedelta(seconds=1),
        )
    )

    assert repository.get_by_session(artifacts[0][0].id) == first
    assert repository.get_by_session(artifacts[1][0].id) == second
    assert repository.list_all() == [first, second]


def test_duplicate_session_preserves_domain_exception_behavior(
    database_session_factory: SessionFactory,
) -> None:
    session, debrief = _persist_artifacts(database_session_factory)[0]
    repository = SQLNegotiationStrategyRepository(database_session_factory)
    original = repository.create(_record(session.id, debrief.id))

    with pytest.raises(NegotiationStrategyAlreadyExistsError) as exc_info:
        repository.create(_record(session.id, debrief.id))

    assert exc_info.value.session_id == session.id
    assert repository.get_by_session(session.id) == original


def test_duplicate_primary_key_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    artifacts = _persist_artifacts(database_session_factory, count=2)
    repository = SQLNegotiationStrategyRepository(database_session_factory)
    record_id = uuid4()
    repository.create(
        _record(artifacts[0][0].id, artifacts[0][1].id, record_id=record_id)
    )

    with pytest.raises(IntegrityError):
        repository.create(
            _record(
                artifacts[1][0].id,
                artifacts[1][1].id,
                record_id=record_id,
            )
        )


def test_missing_session_foreign_key_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    _, debrief = _persist_artifacts(database_session_factory)[0]
    repository = SQLNegotiationStrategyRepository(database_session_factory)

    with pytest.raises(IntegrityError):
        repository.create(_record(uuid4(), debrief.id))


def test_missing_debrief_foreign_key_raises_integrity_error(
    database_session_factory: SessionFactory,
) -> None:
    session, _ = _persist_artifacts(database_session_factory)[0]
    repository = SQLNegotiationStrategyRepository(database_session_factory)

    with pytest.raises(IntegrityError):
        repository.create(_record(session.id, uuid4()))


def test_rollback_preserves_previously_persisted_strategy(
    database_session_factory: SessionFactory,
) -> None:
    session, debrief = _persist_artifacts(database_session_factory)[0]
    repository = SQLNegotiationStrategyRepository(database_session_factory)
    original = repository.create(_record(session.id, debrief.id))

    with pytest.raises(IntegrityError):
        repository.create(_record(uuid4(), uuid4()))

    assert repository.get_by_session(session.id) == original


def test_each_operation_uses_a_fresh_sqlalchemy_session(
    database_session_factory: SessionFactory,
) -> None:
    session, debrief = _persist_artifacts(database_session_factory)[0]
    opened_sessions: list[Session] = []

    def tracking_session_factory() -> Session:
        database_session = database_session_factory()
        opened_sessions.append(database_session)
        return database_session

    repository = SQLNegotiationStrategyRepository(tracking_session_factory)
    repository.create(_record(session.id, debrief.id))
    repository.get_by_session(session.id)
    repository.list_all()

    assert len(opened_sessions) == 3
    assert len({id(database_session) for database_session in opened_sessions}) == 3


def test_strategy_service_behavior_is_unchanged_and_persisted(
    database_session_factory: SessionFactory,
) -> None:
    session, debrief = _persist_artifacts(database_session_factory)[0]
    debrief_repository = SQLNegotiationDebriefRepository(database_session_factory)
    extractor = MagicMock(spec=StrategyExtractor)
    extractor.extract.return_value = _strategy()
    repository = SQLNegotiationStrategyRepository(database_session_factory)
    service = StrategyService(debrief_repository, extractor, repository)

    result = service.generate_for_session(session.id)
    reloaded = SQLNegotiationStrategyRepository(
        database_session_factory
    ).get_by_session(session.id)

    assert result.strategy == _strategy()
    assert result.debrief_id == debrief.id
    assert reloaded == result
    assert service.get_for_session(session.id) == result
    extractor.extract.assert_called_once_with(debrief)
