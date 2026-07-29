import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import configure_logging
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.service import ScenarioService

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
app.state.scenario_service = ScenarioService(scenario_repository)
app.state.negotiation_service = NegotiationService(
    negotiation_repository,
    scenario_repository,
)
app.state.negotiation_turn_service = NegotiationTurnService(
    NegotiationTurnRepository(),
    negotiation_repository,
)

register_exception_handlers(app)
app.include_router(api_v1_router, prefix="/api/v1")
