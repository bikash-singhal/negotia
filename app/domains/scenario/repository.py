from uuid import UUID

from app.domains.scenario.models import Scenario


class ScenarioRepository:
    def __init__(self) -> None:
        self._scenarios: dict[UUID, Scenario] = {}

    def create(self, scenario: Scenario) -> Scenario:
        self._scenarios[scenario.scenario_id] = scenario
        return scenario

    def get(self, scenario_id: UUID) -> Scenario | None:
        return self._scenarios.get(scenario_id)

    def list(self) -> list[Scenario]:
        return list(self._scenarios.values())
