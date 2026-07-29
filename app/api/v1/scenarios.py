from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_scenario_service
from app.domains.scenario.schemas import ScenarioCreate, ScenarioResponse
from app.domains.scenario.service import ScenarioService

router = APIRouter()


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    request: ScenarioCreate,
    service: Annotated[ScenarioService, Depends(get_scenario_service)],
) -> ScenarioResponse:
    scenario = service.create_scenario(request)
    return ScenarioResponse.model_validate(scenario)
