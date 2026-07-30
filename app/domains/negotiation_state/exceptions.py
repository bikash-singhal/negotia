class EmptyNegotiationStateResponseError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned an empty negotiation state response."
        )


class InvalidNegotiationStateJsonError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned invalid JSON for negotiation state extraction."
        )


class InvalidNegotiationStateDataError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned structurally invalid negotiation state data."
        )
