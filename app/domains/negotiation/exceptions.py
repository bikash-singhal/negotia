from uuid import UUID


class ScenarioNotFoundError(Exception):
    def __init__(self, scenario_id: UUID) -> None:
        self.scenario_id = scenario_id
        super().__init__(f"Scenario with id '{scenario_id}' was not found.")
