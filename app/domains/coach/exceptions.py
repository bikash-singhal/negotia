class EmptyCoachObservationResponseError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned an empty coach observation response."
        )


class InvalidCoachObservationJsonError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned invalid JSON for coach observation extraction."
        )


class InvalidCoachObservationDataError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned structurally invalid coach observation data."
        )
