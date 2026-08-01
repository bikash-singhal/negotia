from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.scenario.models import Scenario
from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.schemas import ScenarioCreate, ScenarioGenerateRequest
from app.services.scenario import ScenarioGenerator


class ScenarioService:
    def __init__(
        self,
        repository: ScenarioRepository,
        generator: ScenarioGenerator | None = None,
    ) -> None:
        self._repository = repository
        self._generator = generator

    def generate_scenario(
        self,
        request: ScenarioGenerateRequest,
        user_id: UUID,
    ) -> Scenario:
        if self._generator is None:
            raise RuntimeError("Scenario generation is not configured.")

        generated = self._generator.generate(request)
        return self.create_scenario(
            ScenarioCreate(
                title=request.title,
                description=request.description,
                difficulty=request.difficulty,
                industry=generated.industry,
                opponent_role=generated.opponent_role,
                objective=generated.objective,
                personality=generated.personality,
                negotiation_style=generated.negotiation_style,
                constraints=list(generated.constraints),
                hidden_context=list(generated.hidden_context),
                walk_away_conditions=list(generated.walk_away_conditions),
            ),
            user_id,
        )

    def create_scenario(self, request: ScenarioCreate, user_id: UUID) -> Scenario:
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
            user_id=user_id,
            hidden_context=list(request.hidden_context),
            walk_away_conditions=list(request.walk_away_conditions),
            created_at=now,
            updated_at=now,
        )

        return self._repository.create(scenario)

    def get_scenario(self, scenario_id: UUID, user_id: UUID) -> Scenario | None:
        return self._repository.get_for_user(scenario_id, user_id)

    def list_scenarios(self, user_id: UUID) -> list[Scenario]:
        return self._repository.list_for_user(user_id)
