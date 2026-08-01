class EmptyScenarioGenerationResponseError(Exception):
    def __init__(self) -> None:
        super().__init__("The LLM provider returned an empty scenario response.")


class InvalidScenarioGenerationJsonError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned invalid JSON for scenario generation."
        )


class InvalidScenarioGenerationDataError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned structurally invalid scenario data."
        )
