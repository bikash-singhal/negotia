from uuid import UUID


class EmptyDebriefResponseError(Exception):
    def __init__(self) -> None:
        super().__init__("The LLM provider returned an empty debrief response.")


class InvalidDebriefJsonError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned invalid JSON for debrief extraction."
        )


class InvalidDebriefDataError(Exception):
    def __init__(self) -> None:
        super().__init__("The LLM provider returned structurally invalid debrief data.")


class NoCoachObservationsError(Exception):
    def __init__(self) -> None:
        super().__init__("A debrief cannot be generated without coach observations.")


class NegotiationDebriefAlreadyExistsError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            f"A negotiation debrief already exists for session '{session_id}'."
        )
