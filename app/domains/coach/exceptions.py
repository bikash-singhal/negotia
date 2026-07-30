from uuid import UUID


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


class InvalidCoachExchangeError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Coach observation requires the latest completed user-opponent exchange."
        )


class CoachObservationAlreadyExistsError(Exception):
    def __init__(
        self,
        user_turn_id: UUID,
        opponent_turn_id: UUID,
    ) -> None:
        self.user_turn_id = user_turn_id
        self.opponent_turn_id = opponent_turn_id
        super().__init__(
            "A coach observation already exists for user turn "
            f"'{user_turn_id}' and opponent turn '{opponent_turn_id}'."
        )
