import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.logging_config import configure_logging

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

app.include_router(api_v1_router, prefix="/api/v1")
