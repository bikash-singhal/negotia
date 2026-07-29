from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.negotiations import router as negotiations_router
from app.api.v1.scenarios import router as scenarios_router

router = APIRouter()
router.include_router(health_router)
router.include_router(negotiations_router)
router.include_router(scenarios_router)
