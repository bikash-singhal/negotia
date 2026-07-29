from uuid import UUID


class NegotiationSessionNotFoundError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Negotiation session with id '{session_id}' was not found.")
