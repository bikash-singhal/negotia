import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import configure_logging
from app.domains.coach.repository import CoachObservationRepository
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.opponent.profile_builder import OpponentProfileBuilder
from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.service import ScenarioService
from app.llm.factory import build_llm_provider
from app.prompts.coach import CoachPromptBuilder
from app.prompts.negotiation_state import NegotiationStatePromptBuilder
from app.prompts.opponent import OpponentPromptBuilder
from app.services.coach import CoachObservationExtractor, CoachService
from app.services.negotiation_engine import NegotiationEngine
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentService

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
scenario_repository = ScenarioRepository()
negotiation_repository = NegotiationRepository()
turn_repository = NegotiationTurnRepository()
llm_provider = build_llm_provider(settings)
state_extractor = NegotiationStateExtractor(
    NegotiationStatePromptBuilder(),
    llm_provider,
)
coach_observation_extractor = CoachObservationExtractor(
    CoachPromptBuilder(),
    llm_provider,
)
coach_observation_repository = CoachObservationRepository()
coach_service = CoachService(
    coach_observation_extractor,
    coach_observation_repository,
)
app.state.scenario_service = ScenarioService(scenario_repository)
app.state.negotiation_service = NegotiationService(
    negotiation_repository,
    scenario_repository,
)
app.state.negotiation_turn_service = NegotiationTurnService(
    turn_repository,
    negotiation_repository,
)
opponent_service = OpponentService(
    negotiation_repository,
    scenario_repository,
    turn_repository,
    state_extractor,
    OpponentProfileBuilder(),
    OpponentPromptBuilder(),
    llm_provider,
)
app.state.opponent_service = opponent_service
app.state.coach_service = coach_service
negotiation_engine = NegotiationEngine(
    opponent_service,
    coach_service,
)
app.state.negotiation_engine = negotiation_engine

register_exception_handlers(app)
app.include_router(api_v1_router, prefix="/api/v1")
