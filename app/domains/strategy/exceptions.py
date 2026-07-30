from uuid import UUID


class EmptyStrategyResponseError(Exception):
    def __init__(self) -> None:
        super().__init__("The LLM provider returned an empty strategy response.")


class InvalidStrategyJsonError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned invalid JSON for strategy extraction."
        )


class InvalidStrategyDataError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned structurally invalid strategy data."
        )


class NegotiationDebriefNotFoundError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(f"No negotiation debrief exists for session '{session_id}'.")


class NegotiationStrategyAlreadyExistsError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            f"A negotiation strategy already exists for session '{session_id}'."
        )
