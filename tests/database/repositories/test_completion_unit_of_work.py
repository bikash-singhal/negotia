from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.database.repositories.debrief import SQLNegotiationDebriefRepository
from app.database.repositories.memory import SQLNegotiatorMemoryRepository
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.scenario import SQLScenarioRepository
from app.database.repositories.strategy import SQLNegotiationStrategyRepository
from app.database.unit_of_work import SQLCompletionUnitOfWork
from app.domains.debrief.models import NegotiationDebrief, NegotiationDebriefRecord
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
)

from .conftest import SessionFactory


class ExpectedUnitOfWorkError(Exception):
    pass


def _scenario() -> Scenario:
    return Scenario(
        title="Distribution agreement",
        description="Negotiate pricing and obligations for a distribution agreement.",
        industry="Consumer goods",
        opponent_role="Distribution partner",
        objective="Protect margin while expanding market access.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Commercial and pragmatic",
        negotiation_style="Collaborative but firm",
    )


def _negotiation(scenario_id: UUID) -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        scenario_id=scenario_id,
        status=NegotiationStatus.COMPLETED,
        created_at=now,
        updated_at=now,
    )


def _debrief(session_id: UUID) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=NegotiationDebrief(
            repeated_strengths=["Protected the primary objective."],
            repeated_weaknesses=["Conceded before testing priorities."],
            key_missed_opportunities=["Did not ask about implementation timing."],
            recurring_risks=["Makes unilateral concessions."],
            overall_assessment="Constructive, with room for stronger trades.",
            confidence="high",
        ),
        observation_count=1,
        created_at=datetime.now(UTC),
    )


def _strategy(
    session_id: UUID,
    debrief_id: UUID,
) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=debrief_id,
        strategy=NegotiationStrategy(
            primary_objective="Trade concessions for reciprocal value.",
            expected_outcome="Preserve leverage while improving terms.",
            prioritized_tactics=[],
            long_term_skills=["Concession planning"],
            preparation_checklist=["Define reciprocal asks."],
            avoid_next_time=["Avoid unilateral concessions."],
            confidence="high",
        ),
        created_at=datetime.now(UTC),
    )


def _memory(session_id: UUID) -> NegotiatorMemoryRecord:
    return NegotiatorMemoryRecord(
        id=uuid4(),
        trigger_session_id=session_id,
        memory=NegotiatorMemory(
            recurring_strengths=["Protects primary objectives."],
            recurring_weaknesses=["Concedes before discovery."],
            improving_skills=["Diagnostic questioning"],
            persistent_risks=["Makes unilateral concessions."],
            priority_focus_areas=["Concession planning"],
            recommended_drills=["Prepare conditional trades."],
            sessions_analyzed=1,
            confidence="high",
        ),
        source_session_ids=(session_id,),
        created_at=datetime.now(UTC),
    )


def _write_completion_records(
    unit_of_work: SQLCompletionUnitOfWork,
    scenario_id: UUID,
) -> tuple[
    NegotiationSession,
    NegotiationDebriefRecord,
    NegotiationStrategyRecord,
    NegotiatorMemoryRecord,
]:
    negotiation = unit_of_work.negotiation_repository.create(_negotiation(scenario_id))
    debrief = unit_of_work.debrief_repository.create(_debrief(negotiation.id))
    strategy = unit_of_work.strategy_repository.create(
        _strategy(negotiation.id, debrief.id)
    )
    memory = unit_of_work.memory_repository.create(_memory(negotiation.id))
    return negotiation, debrief, strategy, memory


def test_one_unit_of_work_creates_one_shared_session() -> None:
    database_session = MagicMock(spec=Session)
    session_factory = MagicMock(return_value=database_session)

    with SQLCompletionUnitOfWork(session_factory) as unit_of_work:
        repositories = [
            unit_of_work.negotiation_repository,
            unit_of_work.debrief_repository,
            unit_of_work.strategy_repository,
            unit_of_work.memory_repository,
        ]
        shared_sessions = [
            repository._session_manager.shared_session for repository in repositories
        ]
        unit_of_work.commit()

    session_factory.assert_called_once_with()
    assert shared_sessions == [database_session] * 4
    database_session.commit.assert_called_once_with()
    database_session.close.assert_called_once_with()
    assert unit_of_work._transaction_finished is False

    with pytest.raises(RuntimeError, match="can only be entered once"), unit_of_work:
        pass


def test_separate_unit_of_work_instances_create_separate_sessions() -> None:
    first_session = MagicMock(spec=Session)
    second_session = MagicMock(spec=Session)
    session_factory = MagicMock(side_effect=[first_session, second_session])

    with SQLCompletionUnitOfWork(session_factory):
        pass
    with SQLCompletionUnitOfWork(session_factory):
        pass

    assert session_factory.call_count == 2
    first_session.rollback.assert_called_once_with()
    first_session.close.assert_called_once_with()
    second_session.rollback.assert_called_once_with()
    second_session.close.assert_called_once_with()


def test_successful_exit_without_commit_rolls_back_and_closes_session() -> None:
    database_session = MagicMock(spec=Session)

    with SQLCompletionUnitOfWork(lambda: database_session):
        pass

    database_session.commit.assert_not_called()
    database_session.rollback.assert_called_once_with()
    database_session.close.assert_called_once_with()


def test_exceptional_exit_rolls_back_and_closes_session() -> None:
    database_session = MagicMock(spec=Session)

    with (
        pytest.raises(ExpectedUnitOfWorkError),
        SQLCompletionUnitOfWork(lambda: database_session),
    ):
        raise ExpectedUnitOfWorkError

    database_session.commit.assert_not_called()
    database_session.rollback.assert_called_once_with()
    database_session.close.assert_called_once_with()


def test_session_bound_repositories_flush_without_committing() -> None:
    database_session = MagicMock(spec=Session)
    database_session.scalar.return_value = None
    scenario_id = uuid4()

    with SQLCompletionUnitOfWork(lambda: database_session) as unit_of_work:
        _write_completion_records(unit_of_work, scenario_id)
        database_session.commit.assert_not_called()
        assert database_session.flush.call_count >= 4
        unit_of_work.rollback()

    database_session.commit.assert_not_called()
    database_session.rollback.assert_called_once_with()


def test_commit_persists_all_unit_of_work_writes(
    database_session_factory: SessionFactory,
) -> None:
    scenario = SQLScenarioRepository(database_session_factory).create(_scenario())

    with SQLCompletionUnitOfWork(database_session_factory) as unit_of_work:
        negotiation, debrief, strategy, memory = _write_completion_records(
            unit_of_work,
            scenario.scenario_id,
        )
        unit_of_work.commit()

    assert SQLNegotiationRepository(database_session_factory).get(negotiation.id) == (
        negotiation
    )
    assert (
        SQLNegotiationDebriefRepository(database_session_factory).get_by_session(
            negotiation.id
        )
        == debrief
    )
    assert (
        SQLNegotiationStrategyRepository(database_session_factory).get_by_session(
            negotiation.id
        )
        == strategy
    )
    assert (
        SQLNegotiatorMemoryRepository(database_session_factory).get_by_trigger_session(
            negotiation.id
        )
        == memory
    )


def test_explicit_rollback_removes_all_unit_of_work_writes(
    database_session_factory: SessionFactory,
) -> None:
    scenario = SQLScenarioRepository(database_session_factory).create(_scenario())

    with SQLCompletionUnitOfWork(database_session_factory) as unit_of_work:
        negotiation, _, _, _ = _write_completion_records(
            unit_of_work,
            scenario.scenario_id,
        )
        unit_of_work.rollback()

    assert (
        SQLNegotiationRepository(database_session_factory).get(negotiation.id) is None
    )
    assert (
        SQLNegotiationDebriefRepository(database_session_factory).get_by_session(
            negotiation.id
        )
        is None
    )
    assert (
        SQLNegotiationStrategyRepository(database_session_factory).get_by_session(
            negotiation.id
        )
        is None
    )
    assert (
        SQLNegotiatorMemoryRepository(database_session_factory).get_by_trigger_session(
            negotiation.id
        )
        is None
    )


def test_exception_rolls_back_real_database_writes(
    database_session_factory: SessionFactory,
) -> None:
    scenario = SQLScenarioRepository(database_session_factory).create(_scenario())
    negotiation = _negotiation(scenario.scenario_id)

    with (
        pytest.raises(ExpectedUnitOfWorkError),
        SQLCompletionUnitOfWork(database_session_factory) as unit_of_work,
    ):
        unit_of_work.negotiation_repository.create(negotiation)
        raise ExpectedUnitOfWorkError

    assert (
        SQLNegotiationRepository(database_session_factory).get(negotiation.id) is None
    )


def test_standalone_repositories_still_commit_each_write(
    database_session_factory: SessionFactory,
) -> None:
    scenario = SQLScenarioRepository(database_session_factory).create(_scenario())
    negotiation = SQLNegotiationRepository(database_session_factory).create(
        _negotiation(scenario.scenario_id)
    )
    debrief = SQLNegotiationDebriefRepository(database_session_factory).create(
        _debrief(negotiation.id)
    )
    strategy = SQLNegotiationStrategyRepository(database_session_factory).create(
        _strategy(negotiation.id, debrief.id)
    )
    memory = SQLNegotiatorMemoryRepository(database_session_factory).create(
        _memory(negotiation.id)
    )

    assert SQLNegotiationRepository(database_session_factory).get(negotiation.id) == (
        negotiation
    )
    assert (
        SQLNegotiationDebriefRepository(database_session_factory).get_by_session(
            negotiation.id
        )
        == debrief
    )
    assert (
        SQLNegotiationStrategyRepository(database_session_factory).get_by_session(
            negotiation.id
        )
        == strategy
    )
    assert (
        SQLNegotiatorMemoryRepository(database_session_factory).get_by_trigger_session(
            negotiation.id
        )
        == memory
    )
