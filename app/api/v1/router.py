from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.memory import router as memory_router
from app.api.v1.negotiations import router as negotiations_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.turns import router as turns_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(health_router)
router.include_router(memory_router)
router.include_router(negotiations_router)
router.include_router(scenarios_router)
router.include_router(turns_router)
