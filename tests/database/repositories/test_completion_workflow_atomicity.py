from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.database.repositories.coach import SQLCoachObservationRepository
from app.database.repositories.debrief import SQLNegotiationDebriefRepository
from app.database.repositories.memory import SQLNegotiatorMemoryRepository
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.negotiation_turn import SQLNegotiationTurnRepository
from app.database.repositories.scenario import SQLScenarioRepository
from app.database.repositories.strategy import SQLNegotiationStrategyRepository
from app.database.unit_of_work import SQLCompletionUnitOfWork
from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.debrief.models import NegotiationDebrief, NegotiationDebriefRecord
from app.domains.memory.models import NegotiatorMemory
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.schemas import NegotiationSessionCreate
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
    NegotiationTactic,
)
from app.services.debrief import DebriefExtractor, DebriefService
from app.services.memory import MemoryExtractor, MemoryService
from app.services.strategy import StrategyExtractor, StrategyService
from app.workflows.completion.service import CompletionWorkflowService
from app.workflows.completion.state import CompletionWorkflowState
from tests.ownership import TEST_USER_ID

from .conftest import SessionFactory


class InjectedPersistenceError(Exception):
    pass


def _scenario() -> Scenario:
    return Scenario(
        user_id=TEST_USER_ID,
        title="Atomic completion",
        description="Negotiate a multi-year supplier agreement with support terms.",
        industry="Technology",
        opponent_role="Supplier account executive",
        objective="Secure reciprocal value for every concession.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Commercial and composed",
        negotiation_style="Collaborative but firm",
    )


def _debrief() -> NegotiationDebrief:
    return NegotiationDebrief(
        repeated_strengths=["States objectives clearly."],
        repeated_weaknesses=["Concedes before testing priorities."],
        key_missed_opportunities=["Could ask more diagnostic questions."],
        recurring_risks=["May make unilateral concessions."],
        overall_assessment="A clear exchange with room for stronger trades.",
        confidence="high",
    )


def _strategy() -> NegotiationStrategy:
    return NegotiationStrategy(
        primary_objective="Make every concession conditional.",
        expected_outcome="Preserve leverage while improving terms.",
        prioritized_tactics=[
            NegotiationTactic(
                priority=1,
                title="Trade, do not concede",
                rationale="Reciprocal trades protect value.",
                actions=["Request support value for any price movement."],
                example_language=["I can consider that if support is expanded."],
                success_indicator="Every concession receives reciprocal value.",
            )
        ],
        long_term_skills=["Concession planning"],
        preparation_checklist=["Define reciprocal asks."],
        avoid_next_time=["Avoid unilateral concessions."],
        confidence="high",
    )


def _memory() -> NegotiatorMemory:
    return NegotiatorMemory(
        recurring_strengths=["States objectives clearly."],
        recurring_weaknesses=["Concedes before discovery."],
        improving_skills=["Diagnostic questioning"],
        persistent_risks=["Makes unilateral concessions."],
        priority_focus_areas=["Concession planning"],
        recommended_drills=["Prepare conditional trades."],
        sessions_analyzed=2,
        confidence="high",
    )


def _create_session_with_exchange(
    scenario_id: UUID,
    negotiation_service: NegotiationService,
    turn_repository: SQLNegotiationTurnRepository,
    coach_repository: SQLCoachObservationRepository,
) -> NegotiationSession:
    session = negotiation_service.create_session(
        NegotiationSessionCreate(scenario_id=scenario_id), TEST_USER_ID
    )
    now = datetime.now(UTC)
    user_turn = turn_repository.create(
        NegotiationTurn(
            id=uuid4(),
            session_id=session.id,
            speaker=NegotiationTurnSpeaker.USER,
            content="We need stronger support terms.",
            turn_number=1,
            created_at=now,
        ),
        TEST_USER_ID,
    )
    opponent_turn = turn_repository.create(
        NegotiationTurn(
            id=uuid4(),
            session_id=session.id,
            speaker=NegotiationTurnSpeaker.OPPONENT,
            content="We can discuss support with a longer commitment.",
            turn_number=2,
            created_at=now,
        ),
        TEST_USER_ID,
    )
    coach_repository.create(
        CoachObservationRecord(
            id=uuid4(),
            session_id=session.id,
            user_turn_id=user_turn.id,
            opponent_turn_id=opponent_turn.id,
            observation=CoachObservation(
                strengths=["Clearly stated the objective."],
                weaknesses=["Did not make a conditional proposal."],
                missed_opportunities=["Could test implementation flexibility."],
                risk_signals=["May concede without reciprocal value."],
                confidence="high",
            ),
            created_at=now,
        ),
        TEST_USER_ID,
    )
    return session


def _seed_completed_history(
    scenario_id: UUID,
    negotiation_repository: SQLNegotiationRepository,
    debrief_repository: SQLNegotiationDebriefRepository,
    strategy_repository: SQLNegotiationStrategyRepository,
) -> tuple[NegotiationDebriefRecord, UUID]:
    now = datetime.now(UTC)
    session = negotiation_repository.create(
        NegotiationSession(
            id=uuid4(),
            user_id=TEST_USER_ID,
            scenario_id=scenario_id,
            status=NegotiationStatus.COMPLETED,
            created_at=now,
            updated_at=now,
        )
    )
    debrief = debrief_repository.create(
        NegotiationDebriefRecord(
            id=uuid4(),
            session_id=session.id,
            debrief=_debrief(),
            observation_count=1,
            created_at=now,
        ),
        TEST_USER_ID,
    )
    strategy_repository.create(
        _strategy_record(session.id, debrief.id, now), TEST_USER_ID
    )
    return debrief, session.id


def _strategy_record(
    session_id: UUID,
    debrief_id: UUID,
    created_at: datetime,
) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=debrief_id,
        strategy=_strategy(),
        created_at=created_at,
    )


def _build_workflow(
    database_session_factory: SessionFactory,
) -> tuple[
    CompletionWorkflowService,
    NegotiationService,
    SQLNegotiationRepository,
    SQLNegotiationTurnRepository,
    SQLCoachObservationRepository,
    SQLNegotiationDebriefRepository,
    SQLNegotiationStrategyRepository,
    SQLNegotiatorMemoryRepository,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    scenario_repository = SQLScenarioRepository(database_session_factory)
    negotiation_repository = SQLNegotiationRepository(database_session_factory)
    turn_repository = SQLNegotiationTurnRepository(database_session_factory)
    coach_repository = SQLCoachObservationRepository(database_session_factory)
    debrief_repository = SQLNegotiationDebriefRepository(database_session_factory)
    strategy_repository = SQLNegotiationStrategyRepository(database_session_factory)
    memory_repository = SQLNegotiatorMemoryRepository(database_session_factory)
    negotiation_service = NegotiationService(
        negotiation_repository,
        scenario_repository,
    )
    debrief_extractor = MagicMock(spec=DebriefExtractor)
    debrief_extractor.extract.return_value = _debrief()
    strategy_extractor = MagicMock(spec=StrategyExtractor)
    strategy_extractor.extract.return_value = _strategy()
    memory_extractor = MagicMock(spec=MemoryExtractor)
    memory_extractor.extract.return_value = _memory()
    workflow = CompletionWorkflowService(
        negotiation_service,
        NegotiationTurnService(turn_repository, negotiation_repository),
        DebriefService(coach_repository, debrief_extractor, debrief_repository),
        StrategyService(debrief_repository, strategy_extractor, strategy_repository),
        MemoryService(
            debrief_repository,
            strategy_repository,
            memory_extractor,
            memory_repository,
        ),
        lambda: SQLCompletionUnitOfWork(database_session_factory),
    )
    return (
        workflow,
        negotiation_service,
        negotiation_repository,
        turn_repository,
        coach_repository,
        debrief_repository,
        strategy_repository,
        memory_repository,
        debrief_extractor,
        strategy_extractor,
        memory_extractor,
    )


@pytest.mark.parametrize(
    ("repository_type", "method_name"),
    [
        (SQLNegotiationStrategyRepository, "create"),
        (SQLNegotiatorMemoryRepository, "create"),
        (SQLNegotiationRepository, "update_for_user"),
    ],
)
def test_completion_write_failure_rolls_back_all_new_artifacts(
    database_session_factory: SessionFactory,
    repository_type: type[object],
    method_name: str,
) -> None:
    (
        workflow,
        negotiation_service,
        negotiation_repository,
        turn_repository,
        coach_repository,
        debrief_repository,
        strategy_repository,
        memory_repository,
        _,
        _,
        _,
    ) = _build_workflow(database_session_factory)
    scenario = SQLScenarioRepository(database_session_factory).create(_scenario())
    legacy_debrief, legacy_session_id = _seed_completed_history(
        scenario.scenario_id,
        negotiation_repository,
        debrief_repository,
        strategy_repository,
    )
    target = _create_session_with_exchange(
        scenario.scenario_id,
        negotiation_service,
        turn_repository,
        coach_repository,
    )

    with (
        patch.object(
            repository_type,
            method_name,
            autospec=True,
            side_effect=InjectedPersistenceError,
        ),
        pytest.raises(InjectedPersistenceError),
    ):
        workflow.run(target.id, TEST_USER_ID)

    fresh_negotiation = SQLNegotiationRepository(database_session_factory).get_for_user(
        target.id, TEST_USER_ID
    )
    assert fresh_negotiation is not None
    assert fresh_negotiation.status is NegotiationStatus.CREATED
    assert debrief_repository.get_by_session_for_user(target.id, TEST_USER_ID) is None
    assert strategy_repository.get_by_session_for_user(target.id, TEST_USER_ID) is None
    assert memory_repository.get_by_trigger_session(target.id, TEST_USER_ID) is None
    assert (
        debrief_repository.get_by_session_for_user(legacy_session_id, TEST_USER_ID)
        == legacy_debrief
    )
    assert (
        strategy_repository.get_by_session_for_user(legacy_session_id, TEST_USER_ID)
        is not None
    )


def test_failed_recovery_preserves_legacy_target_debrief_and_retry_succeeds(
    database_session_factory: SessionFactory,
) -> None:
    (
        workflow,
        negotiation_service,
        negotiation_repository,
        turn_repository,
        coach_repository,
        debrief_repository,
        strategy_repository,
        memory_repository,
        debrief_extractor,
        strategy_extractor,
        memory_extractor,
    ) = _build_workflow(database_session_factory)
    scenario = SQLScenarioRepository(database_session_factory).create(_scenario())
    _seed_completed_history(
        scenario.scenario_id,
        negotiation_repository,
        debrief_repository,
        strategy_repository,
    )
    target = _create_session_with_exchange(
        scenario.scenario_id,
        negotiation_service,
        turn_repository,
        coach_repository,
    )
    legacy_target_debrief = debrief_repository.create(
        NegotiationDebriefRecord(
            id=uuid4(),
            session_id=target.id,
            debrief=_debrief(),
            observation_count=1,
            created_at=datetime.now(UTC),
        ),
        TEST_USER_ID,
    )

    with (
        patch.object(
            SQLNegotiationStrategyRepository,
            "create",
            autospec=True,
            side_effect=InjectedPersistenceError,
        ),
        pytest.raises(InjectedPersistenceError),
    ):
        workflow.run(target.id, TEST_USER_ID)

    assert (
        debrief_repository.get_by_session_for_user(target.id, TEST_USER_ID)
        == legacy_target_debrief
    )
    assert strategy_repository.get_by_session_for_user(target.id, TEST_USER_ID) is None
    assert memory_repository.get_by_trigger_session(target.id, TEST_USER_ID) is None
    debrief_extractor.extract.assert_not_called()

    result = workflow.run(target.id, TEST_USER_ID)
    repeated = workflow.run(target.id, TEST_USER_ID)

    assert result.session.status is NegotiationStatus.COMPLETED
    assert result.debrief_record == legacy_target_debrief
    assert result == repeated
    assert (
        strategy_repository.get_by_session_for_user(target.id, TEST_USER_ID)
        == result.strategy_record
    )
    assert (
        memory_repository.get_by_trigger_session(target.id, TEST_USER_ID)
        == result.memory_record
    )
    assert strategy_extractor.extract.call_count == 2
    assert memory_extractor.extract.call_count == 2
    debrief_extractor.extract.assert_not_called()


def test_interleaved_preparation_reconciles_after_first_finalizer_completes(
    database_session_factory: SessionFactory,
) -> None:
    (
        workflow,
        negotiation_service,
        negotiation_repository,
        turn_repository,
        coach_repository,
        debrief_repository,
        strategy_repository,
        memory_repository,
        debrief_extractor,
        strategy_extractor,
        memory_extractor,
    ) = _build_workflow(database_session_factory)
    scenario = SQLScenarioRepository(database_session_factory).create(_scenario())
    _seed_completed_history(
        scenario.scenario_id,
        negotiation_repository,
        debrief_repository,
        strategy_repository,
    )
    target = _create_session_with_exchange(
        scenario.scenario_id,
        negotiation_service,
        turn_repository,
        coach_repository,
    )

    def prepare() -> CompletionWorkflowState:
        state = CompletionWorkflowState(
            session_id=target.id,
            user_id=TEST_USER_ID,
        )
        validation = workflow._nodes.validate_session(state)
        assert "session" in validation
        state["session"] = validation["session"]
        debrief = workflow._nodes.create_or_reuse_debrief(state)
        assert "debrief_record" in debrief
        assert "debrief_prepared" in debrief
        state["debrief_record"] = debrief["debrief_record"]
        state["debrief_prepared"] = debrief["debrief_prepared"]
        strategy = workflow._nodes.create_or_reuse_strategy(state)
        assert "strategy_record" in strategy
        assert "strategy_prepared" in strategy
        state["strategy_record"] = strategy["strategy_record"]
        state["strategy_prepared"] = strategy["strategy_prepared"]
        memory = workflow._nodes.create_or_reuse_memory(state)
        assert "memory_record" in memory
        assert "memory_prepared" in memory
        state["memory_record"] = memory["memory_record"]
        state["memory_prepared"] = memory["memory_prepared"]
        return state

    first_prepared = prepare()
    second_prepared = prepare()
    first_result = workflow._nodes.finalize_completion(first_prepared)
    second_result = workflow._nodes.finalize_completion(second_prepared)

    assert "session" in first_result
    assert "debrief_record" in first_result
    assert "strategy_record" in first_result
    assert "memory_record" in first_result
    assert "session" in second_result
    assert "debrief_record" in second_result
    assert "strategy_record" in second_result
    assert "memory_record" in second_result

    first_session = first_result["session"]
    first_debrief = first_result["debrief_record"]
    first_strategy = first_result["strategy_record"]
    first_memory = first_result["memory_record"]
    second_session = second_result["session"]
    completed_at = first_session.updated_at

    assert second_session.status is NegotiationStatus.COMPLETED
    assert second_session.updated_at == completed_at
    assert second_result["debrief_record"] == first_debrief
    assert second_result["strategy_record"] == first_strategy
    assert second_result["memory_record"] == first_memory
    assert (
        debrief_repository.get_by_session_for_user(target.id, TEST_USER_ID)
        == first_debrief
    )
    assert (
        strategy_repository.get_by_session_for_user(target.id, TEST_USER_ID)
        == first_strategy
    )
    assert (
        memory_repository.get_by_trigger_session(target.id, TEST_USER_ID)
        == first_memory
    )
    assert debrief_extractor.extract.call_count == 2
    assert strategy_extractor.extract.call_count == 2
    assert memory_extractor.extract.call_count == 2
