from typing import cast

from fastapi import Request

from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.scenario.service import ScenarioService


def get_scenario_service(request: Request) -> ScenarioService:
    return cast(ScenarioService, request.app.state.scenario_service)


def get_negotiation_service(request: Request) -> NegotiationService:
    return cast(NegotiationService, request.app.state.negotiation_service)


def get_negotiation_turn_service(request: Request) -> NegotiationTurnService:
    return cast(
        NegotiationTurnService,
        request.app.state.negotiation_turn_service,
    )
