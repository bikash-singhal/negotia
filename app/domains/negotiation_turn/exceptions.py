from uuid import UUID

from app.domains.negotiation_turn.models import NegotiationTurnSpeaker


class NegotiationSessionNotFoundError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Negotiation session with id '{session_id}' was not found.")


class OpponentResponseRequiresUserTurnError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            "An opponent response cannot be generated for negotiation session "
            f"'{session_id}' without a user turn."
        )


class OpponentResponseOutOfSequenceError(Exception):
    def __init__(
        self,
        session_id: UUID,
        latest_speaker: NegotiationTurnSpeaker,
    ) -> None:
        self.session_id = session_id
        self.latest_speaker = latest_speaker
        super().__init__(
            "An opponent response cannot be generated for negotiation session "
            f"'{session_id}' because the latest turn is from "
            f"'{latest_speaker.value}'."
        )


class EmptyOpponentResponseError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            "The LLM provider returned an empty opponent response for negotiation "
            f"session '{session_id}'."
        )
