from uuid import UUID

from app.domains.scenario.models import Scenario


class ScenarioRepository:
    def __init__(self) -> None:
        self._scenarios: dict[UUID, Scenario] = {}

    def create(self, scenario: Scenario) -> Scenario:
        self._scenarios[scenario.scenario_id] = scenario
        return scenario

    def get_for_user(self, scenario_id: UUID, user_id: UUID) -> Scenario | None:
        scenario = self._scenarios.get(scenario_id)
        if scenario is None or scenario.user_id != user_id:
            return None
        return scenario

    def list_for_user(self, user_id: UUID) -> list[Scenario]:
        return [
            scenario
            for scenario in self._scenarios.values()
            if scenario.user_id == user_id
        ]
