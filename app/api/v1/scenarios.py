from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_scenario_service
from app.domains.scenario.schemas import ScenarioCreate, ScenarioResponse
from app.domains.scenario.service import ScenarioService

router = APIRouter()


@router.get(
    "/scenarios",
    response_model=list[ScenarioResponse],
    status_code=status.HTTP_200_OK,
)
async def list_scenarios(
    service: Annotated[ScenarioService, Depends(get_scenario_service)],
) -> list[ScenarioResponse]:
    return [
        ScenarioResponse.model_validate(scenario)
        for scenario in service.list_scenarios()
    ]


@router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
    status_code=status.HTTP_200_OK,
)
async def get_scenario(
    scenario_id: UUID,
    service: Annotated[ScenarioService, Depends(get_scenario_service)],
) -> ScenarioResponse:
    scenario = service.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario with id '{scenario_id}' was not found.",
        )

    return ScenarioResponse.model_validate(scenario)


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
