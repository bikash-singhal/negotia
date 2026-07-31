from app.database.repositories.coach import SQLCoachObservationRepository
from app.database.repositories.debrief import SQLNegotiationDebriefRepository
from app.database.repositories.memory import SQLNegotiatorMemoryRepository
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.negotiation_turn import SQLNegotiationTurnRepository
from app.database.repositories.scenario import SQLScenarioRepository
from app.database.repositories.strategy import SQLNegotiationStrategyRepository
from app.llm.fake import FakeLLMProvider
from app.main import (
    adaptive_context_service,
    app,
    coach_observation_extractor,
    coach_observation_repository,
    coach_service,
    completion_workflow_service,
    debrief_extractor,
    debrief_repository,
    debrief_service,
    llm_provider,
    memory_extractor,
    memory_repository,
    memory_service,
    negotiation_engine,
    negotiation_repository,
    negotiation_service,
    negotiation_turn_service,
    opponent_service,
    scenario_repository,
    state_extractor,
    strategy_extractor,
    strategy_repository,
    strategy_service,
    turn_repository,
)
from app.services.adaptive_context import AdaptiveContextService
from app.services.coach import CoachObservationExtractor, CoachService
from app.services.debrief import DebriefExtractor, DebriefService
from app.services.memory import MemoryExtractor, MemoryService
from app.services.negotiation_engine import NegotiationEngine
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentService
from app.services.strategy import StrategyExtractor, StrategyService
from app.workflows.completion.service import CompletionWorkflowService


def test_app_builds_llm_services_with_configured_provider() -> None:
    assert isinstance(scenario_repository, SQLScenarioRepository)
    assert isinstance(negotiation_repository, SQLNegotiationRepository)
    assert isinstance(turn_repository, SQLNegotiationTurnRepository)
    assert isinstance(coach_observation_repository, SQLCoachObservationRepository)
    assert isinstance(debrief_repository, SQLNegotiationDebriefRepository)
    assert isinstance(strategy_repository, SQLNegotiationStrategyRepository)
    assert isinstance(memory_repository, SQLNegotiatorMemoryRepository)
    assert negotiation_turn_service._turn_repository is turn_repository
    assert isinstance(adaptive_context_service, AdaptiveContextService)
    assert isinstance(llm_provider, FakeLLMProvider)
    assert isinstance(coach_observation_extractor, CoachObservationExtractor)
    assert isinstance(coach_service, CoachService)
    assert isinstance(completion_workflow_service, CompletionWorkflowService)
    assert isinstance(debrief_extractor, DebriefExtractor)
    assert isinstance(debrief_service, DebriefService)
    assert isinstance(memory_extractor, MemoryExtractor)
    assert isinstance(memory_service, MemoryService)
    assert isinstance(negotiation_engine, NegotiationEngine)
    assert isinstance(state_extractor, NegotiationStateExtractor)
    assert isinstance(strategy_extractor, StrategyExtractor)
    assert isinstance(strategy_service, StrategyService)
    assert isinstance(opponent_service, OpponentService)
    assert coach_observation_extractor._llm_provider is llm_provider
    assert coach_service._extractor is coach_observation_extractor
    assert coach_service._repository is coach_observation_repository
    assert coach_service._adaptive_context_service is adaptive_context_service
    assert app.state.coach_service is coach_service
    assert not hasattr(app.state, "coach_observation_repository")
    assert debrief_extractor._llm_provider is llm_provider
    assert debrief_service._coach_observation_repository is (
        coach_observation_repository
    )
    assert debrief_service._extractor is debrief_extractor
    assert debrief_service._debrief_repository is debrief_repository
    assert app.state.debrief_service is debrief_service
    assert not hasattr(app.state, "debrief_repository")
    assert negotiation_engine._opponent_service is opponent_service
    assert negotiation_engine._coach_service is coach_service
    assert (
        negotiation_engine._completion_workflow_service is completion_workflow_service
    )
    assert (
        completion_workflow_service._nodes._negotiation_service is negotiation_service
    )
    assert (
        completion_workflow_service._nodes._negotiation_turn_service
        is negotiation_turn_service
    )
    assert completion_workflow_service._nodes._debrief_service is debrief_service
    assert completion_workflow_service._nodes._strategy_service is strategy_service
    assert completion_workflow_service._nodes._memory_service is memory_service
    assert app.state.negotiation_engine is negotiation_engine
    assert state_extractor._llm_provider is llm_provider
    assert opponent_service._state_extractor is state_extractor
    assert opponent_service._turn_repository is turn_repository
    assert opponent_service._llm_provider is llm_provider
    assert opponent_service._adaptive_context_service is adaptive_context_service
    assert strategy_extractor._llm_provider is llm_provider
    assert strategy_service._debrief_repository is debrief_repository
    assert strategy_service._extractor is strategy_extractor
    assert strategy_service._strategy_repository is strategy_repository
    assert app.state.strategy_service is strategy_service
    assert not hasattr(app.state, "strategy_repository")
    assert memory_extractor._llm_provider is llm_provider
    assert memory_service._debrief_repository is debrief_repository
    assert memory_service._strategy_repository is strategy_repository
    assert memory_service._extractor is memory_extractor
    assert memory_service._memory_repository is memory_repository
    assert app.state.memory_service is memory_service
    assert not hasattr(app.state, "memory_repository")
    assert not hasattr(negotiation_engine, "_negotiation_service")
    assert not hasattr(negotiation_engine, "_negotiation_turn_service")
    assert not hasattr(negotiation_engine, "_debrief_service")
    assert not hasattr(negotiation_engine, "_strategy_service")
    assert not hasattr(negotiation_engine, "_memory_service")
    assert adaptive_context_service._memory_service is memory_service
    assert app.state.adaptive_context_service is adaptive_context_service
    assert not hasattr(negotiation_engine, "_adaptive_context_service")


def test_app_has_no_debrief_endpoint() -> None:
    route_paths = app.openapi().get("paths", {})

    assert all("debrief" not in path for path in route_paths)


def test_app_registers_completion_endpoint() -> None:
    route_paths = app.openapi().get("paths", {})

    assert "/api/v1/negotiations/{session_id}/complete" in route_paths


def test_app_has_no_strategy_endpoint() -> None:
    route_paths = app.openapi().get("paths", {})

    assert all("strategy" not in path for path in route_paths)


def test_app_has_no_memory_endpoint() -> None:
    route_paths = app.openapi().get("paths", {})

    assert all("memory" not in path for path in route_paths)


def test_app_has_no_adaptive_context_endpoint() -> None:
    route_paths = app.openapi().get("paths", {})

    assert all("adaptive" not in path for path in route_paths)
