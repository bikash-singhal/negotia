import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import configure_logging
from app.database.repositories.coach import SQLCoachObservationRepository
from app.database.repositories.debrief import SQLNegotiationDebriefRepository
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.negotiation_turn import SQLNegotiationTurnRepository
from app.database.repositories.scenario import SQLScenarioRepository
from app.database.repositories.strategy import SQLNegotiationStrategyRepository
from app.domains.memory.repository import NegotiatorMemoryRepository
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.opponent.profile_builder import OpponentProfileBuilder
from app.domains.scenario.service import ScenarioService
from app.llm.factory import build_llm_provider
from app.prompts.coach import CoachPromptBuilder
from app.prompts.debrief import DebriefPromptBuilder
from app.prompts.memory import MemoryPromptBuilder
from app.prompts.negotiation_state import NegotiationStatePromptBuilder
from app.prompts.opponent import OpponentPromptBuilder
from app.prompts.strategy import StrategyPromptBuilder
from app.services.adaptive_context import AdaptiveContextService
from app.services.coach import CoachObservationExtractor, CoachService
from app.services.debrief import DebriefExtractor, DebriefService
from app.services.memory import MemoryExtractor, MemoryService
from app.services.negotiation_engine import NegotiationEngine
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentService
from app.services.strategy import StrategyExtractor, StrategyService
from app.workflows.completion.service import CompletionWorkflowService

configure_logging(settings.debug)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    logger.info("Negotia API is starting")

    try:
        yield
    finally:
        logger.info("Negotia API is shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    lifespan=lifespan,
)
scenario_repository = SQLScenarioRepository()
negotiation_repository = SQLNegotiationRepository()
turn_repository = SQLNegotiationTurnRepository()
llm_provider = build_llm_provider(settings)
state_extractor = NegotiationStateExtractor(
    NegotiationStatePromptBuilder(),
    llm_provider,
)
coach_observation_extractor = CoachObservationExtractor(
    CoachPromptBuilder(),
    llm_provider,
)
coach_observation_repository = SQLCoachObservationRepository()
debrief_extractor = DebriefExtractor(
    DebriefPromptBuilder(),
    llm_provider,
)
debrief_repository = SQLNegotiationDebriefRepository()
debrief_service = DebriefService(
    coach_observation_repository,
    debrief_extractor,
    debrief_repository,
)
strategy_extractor = StrategyExtractor(
    StrategyPromptBuilder(),
    llm_provider,
)
strategy_repository = SQLNegotiationStrategyRepository()
strategy_service = StrategyService(
    debrief_repository,
    strategy_extractor,
    strategy_repository,
)
memory_extractor = MemoryExtractor(
    MemoryPromptBuilder(),
    llm_provider,
)
memory_repository = NegotiatorMemoryRepository()
memory_service = MemoryService(
    debrief_repository,
    strategy_repository,
    memory_extractor,
    memory_repository,
)
adaptive_context_service = AdaptiveContextService(memory_service)
coach_service = CoachService(
    coach_observation_extractor,
    coach_observation_repository,
    adaptive_context_service,
)
app.state.scenario_service = ScenarioService(scenario_repository)
negotiation_service = NegotiationService(
    negotiation_repository,
    scenario_repository,
)
app.state.negotiation_service = negotiation_service
negotiation_turn_service = NegotiationTurnService(
    turn_repository,
    negotiation_repository,
)
app.state.negotiation_turn_service = negotiation_turn_service
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
app.state.opponent_service = opponent_service
app.state.coach_service = coach_service
app.state.debrief_service = debrief_service
app.state.strategy_service = strategy_service
app.state.memory_service = memory_service
app.state.adaptive_context_service = adaptive_context_service
completion_workflow_service = CompletionWorkflowService(
    negotiation_service,
    negotiation_turn_service,
    debrief_service,
    strategy_service,
    memory_service,
)
negotiation_engine = NegotiationEngine(
    opponent_service,
    coach_service,
    completion_workflow_service,
)
app.state.negotiation_engine = negotiation_engine

register_exception_handlers(app)
app.include_router(api_v1_router, prefix="/api/v1")
