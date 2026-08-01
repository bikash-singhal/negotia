from unittest.mock import MagicMock

from app.database.repositories.coach import SQLCoachObservationRepository
from app.database.repositories.debrief import SQLNegotiationDebriefRepository
from app.database.repositories.memory import SQLNegotiatorMemoryRepository
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.negotiation_turn import SQLNegotiationTurnRepository
from app.database.repositories.scenario import SQLScenarioRepository
from app.database.repositories.strategy import SQLNegotiationStrategyRepository
from app.database.unit_of_work import SQLCompletionUnitOfWork
from app.domains.adaptive_context.models import AdaptiveContext
from app.domains.coach.models import CoachObservation
from app.domains.debrief.models import NegotiationDebrief
from app.domains.memory.models import NegotiatorMemory
from app.domains.negotiation.models import NegotiationStatus
from app.domains.negotiation.schemas import NegotiationSessionCreate
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_state.models import NegotiationState
from app.domains.negotiation_turn.models import NegotiationTurnSpeaker
from app.domains.negotiation_turn.schemas import NegotiationTurnCreate
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.opponent.profile_builder import OpponentProfileBuilder
from app.domains.scenario.models import ScenarioDifficulty
from app.domains.scenario.schemas import ScenarioCreate
from app.domains.scenario.service import ScenarioService
from app.domains.strategy.models import NegotiationStrategy, NegotiationTactic
from app.llm.provider import LLMProvider
from app.prompts.opponent import OpponentPromptBuilder
from app.services.adaptive_context import AdaptiveContextService
from app.services.coach import CoachObservationExtractor, CoachService
from app.services.debrief import DebriefExtractor, DebriefService
from app.services.memory import MemoryExtractor, MemoryService
from app.services.negotiation_engine import NegotiationEngine
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentService
from app.services.strategy import StrategyExtractor, StrategyService
from app.workflows.completion.service import CompletionWorkflowService
from tests.ownership import TEST_USER_ID

from .conftest import SessionFactory


def _scenario_request() -> ScenarioCreate:
    return ScenarioCreate(
        title="Enterprise software renewal",
        description="Negotiate price, support, and renewal terms for core software.",
        industry="Technology",
        opponent_role="Vendor account executive",
        objective="Control cost while preserving service quality.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        constraints=["The renewal deadline is approaching."],
        personality="Commercially focused and composed",
        negotiation_style="Collaborative but firm",
        hidden_context=["The vendor has flexibility on support credits."],
        walk_away_conditions=["No uncapped annual price increase."],
    )


def _negotiation_state() -> NegotiationState:
    return NegotiationState(
        latest_user_position="The user requested better commercial terms.",
        latest_opponent_position=None,
        agreements=[],
        open_topics=["Price", "Support"],
        unresolved_items=["Renewal cap"],
        negotiation_stage="bargaining",
    )


def _coach_observation() -> CoachObservation:
    return CoachObservation(
        strengths=["Clearly stated the commercial objective."],
        weaknesses=["Did not make the concession conditional."],
        missed_opportunities=["Could have tested support flexibility."],
        risk_signals=["May concede without reciprocal value."],
        confidence="high",
    )


def _debrief() -> NegotiationDebrief:
    return NegotiationDebrief(
        repeated_strengths=["Clearly stated the commercial objective."],
        repeated_weaknesses=["Made an unconditional request."],
        key_missed_opportunities=["Did not test support flexibility."],
        recurring_risks=["May concede without reciprocal value."],
        overall_assessment="A clear opening with room for stronger trades.",
        confidence="high",
    )


def _strategy() -> NegotiationStrategy:
    return NegotiationStrategy(
        primary_objective="Trade every concession for reciprocal value.",
        expected_outcome="Improve terms without eroding negotiating leverage.",
        prioritized_tactics=[
            NegotiationTactic(
                priority=1,
                title="Make concessions conditional",
                rationale="Conditional trades protect value.",
                actions=["Request a support credit for any price movement."],
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
        stable_strengths=["States objectives clearly."],
        stable_weaknesses=["Makes unconditional requests."],
        improving_skills=["Diagnostic questioning"],
        persistent_risks=["Concedes without reciprocal value."],
        highest_priority_skill="Concession planning",
        next_session_drill="Prepare conditional trades.",
        progress_summary="Questioning is improving; concessions remain a risk.",
        sessions_analyzed=2,
        confidence="high",
    )


def test_complete_negotiation_lifecycle_persists_all_aggregates_idempotently(
    database_session_factory: SessionFactory,
) -> None:
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
    turn_service = NegotiationTurnService(
        turn_repository,
        negotiation_repository,
    )

    state_extractor = MagicMock(spec=NegotiationStateExtractor)
    state_extractor.extract.return_value = _negotiation_state()
    coach_extractor = MagicMock(spec=CoachObservationExtractor)
    coach_extractor.extract.return_value = _coach_observation()
    debrief_extractor = MagicMock(spec=DebriefExtractor)
    debrief_extractor.extract.return_value = _debrief()
    strategy_extractor = MagicMock(spec=StrategyExtractor)
    strategy_extractor.extract.return_value = _strategy()
    memory_extractor = MagicMock(spec=MemoryExtractor)
    memory_extractor.extract.return_value = _memory()
    llm_provider = MagicMock(spec=LLMProvider)
    llm_provider.generate.return_value = (
        "We can improve support terms if the renewal commitment increases."
    )

    memory_service = MemoryService(
        debrief_repository,
        strategy_repository,
        memory_extractor,
        memory_repository,
    )
    adaptive_context_service = AdaptiveContextService(memory_service)
    coach_service = CoachService(
        coach_extractor,
        coach_repository,
        adaptive_context_service,
    )
    opponent_service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        state_extractor,
        OpponentProfileBuilder(),
        OpponentPromptBuilder(),
        llm_provider,
        adaptive_context_service,
    )
    debrief_service = DebriefService(
        coach_repository,
        debrief_extractor,
        debrief_repository,
    )
    strategy_service = StrategyService(
        debrief_repository,
        strategy_extractor,
        strategy_repository,
    )
    completion_workflow = CompletionWorkflowService(
        negotiation_service,
        turn_service,
        debrief_service,
        strategy_service,
        memory_service,
        lambda: SQLCompletionUnitOfWork(database_session_factory),
    )
    engine = NegotiationEngine(
        opponent_service,
        coach_service,
        completion_workflow,
    )

    scenario = ScenarioService(scenario_repository).create_scenario(
        _scenario_request(), TEST_USER_ID
    )
    sessions = []
    completion_results = []
    for session_number in range(1, 3):
        session = negotiation_service.create_session(
            NegotiationSessionCreate(scenario_id=scenario.scenario_id),
            TEST_USER_ID,
        )
        turn_service.create_turn(
            NegotiationTurnCreate(
                session_id=session.id,
                speaker=NegotiationTurnSpeaker.USER,
                content=f"For negotiation {session_number}, we need better terms.",
            ),
            TEST_USER_ID,
        )
        engine.generate_response(session.id, TEST_USER_ID)
        sessions.append(session)
        completion_results.append(engine.complete_session(session.id, TEST_USER_ID))

    target_session = sessions[-1]
    first_completion = completion_results[-1]
    assert completion_results[0].memory_record is None
    assert first_completion.memory_record is not None
    original_completed_at = first_completion.session.updated_at

    repeated_completion = engine.complete_session(target_session.id, TEST_USER_ID)

    fresh_scenario_repository = SQLScenarioRepository(database_session_factory)
    fresh_negotiation_repository = SQLNegotiationRepository(database_session_factory)
    fresh_turn_repository = SQLNegotiationTurnRepository(database_session_factory)
    fresh_coach_repository = SQLCoachObservationRepository(database_session_factory)
    fresh_debrief_repository = SQLNegotiationDebriefRepository(database_session_factory)
    fresh_strategy_repository = SQLNegotiationStrategyRepository(
        database_session_factory
    )
    fresh_memory_repository = SQLNegotiatorMemoryRepository(database_session_factory)

    persisted_scenario = fresh_scenario_repository.get_for_user(
        scenario.scenario_id, TEST_USER_ID
    )
    persisted_session = fresh_negotiation_repository.get_for_user(
        target_session.id, TEST_USER_ID
    )
    persisted_turns = fresh_turn_repository.list_by_session_for_user(
        target_session.id, TEST_USER_ID
    )
    persisted_observations = fresh_coach_repository.list_by_session_for_user(
        target_session.id, TEST_USER_ID
    )
    persisted_debrief = fresh_debrief_repository.get_by_session_for_user(
        target_session.id, TEST_USER_ID
    )
    persisted_strategy = fresh_strategy_repository.get_by_session_for_user(
        target_session.id, TEST_USER_ID
    )
    persisted_memory = fresh_memory_repository.get_by_trigger_session(
        target_session.id, TEST_USER_ID
    )

    assert persisted_scenario == scenario
    assert persisted_session is not None
    assert persisted_session.status is NegotiationStatus.COMPLETED
    assert persisted_session.updated_at == original_completed_at
    assert [turn.turn_number for turn in persisted_turns] == [1, 2]
    assert [turn.speaker for turn in persisted_turns] == [
        NegotiationTurnSpeaker.USER,
        NegotiationTurnSpeaker.OPPONENT,
    ]
    assert len(persisted_observations) == 1
    assert persisted_debrief == first_completion.debrief_record
    assert persisted_strategy == first_completion.strategy_record
    assert persisted_memory == first_completion.memory_record

    assert repeated_completion.session == first_completion.session
    assert repeated_completion.debrief_record == first_completion.debrief_record
    assert repeated_completion.strategy_record == first_completion.strategy_record
    assert repeated_completion.memory_record == first_completion.memory_record
    assert (
        len(
            fresh_coach_repository.list_by_session_for_user(
                target_session.id, TEST_USER_ID
            )
        )
        == 1
    )
    assert len(fresh_strategy_repository.list_for_user(TEST_USER_ID)) == 2
    assert len(fresh_memory_repository.list_for_user(TEST_USER_ID)) == 1
    assert debrief_extractor.extract.call_count == 2
    assert strategy_extractor.extract.call_count == 2
    assert memory_extractor.extract.call_count == 1

    fresh_memory_service = MemoryService(
        fresh_debrief_repository,
        fresh_strategy_repository,
        memory_extractor,
        fresh_memory_repository,
    )
    adaptive_context = AdaptiveContextService(fresh_memory_service).get_context(
        TEST_USER_ID
    )
    assert adaptive_context == AdaptiveContext(
        focus_areas=["Concession planning"],
        coaching_focus=["Diagnostic questioning"],
        opponent_adjustments=["Concedes without reciprocal value."],
        strengths=["States objectives clearly."],
    )
