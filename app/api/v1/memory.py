from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_memory_service
from app.domains.memory.models import NegotiatorMemory
from app.domains.user.models import User
from app.services.memory import MemoryService

router = APIRouter()


@router.get(
    "/memory/latest",
    response_model=NegotiatorMemory | None,
    status_code=status.HTTP_200_OK,
)
async def get_latest_memory(
    service: Annotated[MemoryService, Depends(get_memory_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NegotiatorMemory | None:
    record = service.get_latest(current_user.id)
    return None if record is None else record.memory
