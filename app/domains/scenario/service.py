from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.scenario.models import Scenario
from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.schemas import ScenarioCreate


class ScenarioService:
    def __init__(self, repository: ScenarioRepository) -> None:
        self._repository = repository

    def create_scenario(self, request: ScenarioCreate) -> Scenario:
        now = datetime.now(UTC)
        scenario = Scenario(
            scenario_id=uuid4(),
            title=request.title,
            description=request.description,
            industry=request.industry,
            opponent_role=request.opponent_role,
            objective=request.objective,
            difficulty=request.difficulty,
            constraints=list(request.constraints),
            personality=request.personality,
            negotiation_style=request.negotiation_style,
            hidden_context=list(request.hidden_context),
            walk_away_conditions=list(request.walk_away_conditions),
            created_at=now,
            updated_at=now,
        )

        return self._repository.create(scenario)

    def get_scenario(self, scenario_id: UUID) -> Scenario | None:
        return self._repository.get(scenario_id)

    def list_scenarios(self) -> list[Scenario]:
        return self._repository.list()
