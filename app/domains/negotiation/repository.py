from uuid import UUID

from app.domains.negotiation.models import NegotiationSession
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError


class NegotiationRepository:
    def __init__(self) -> None:
        self._sessions: dict[UUID, NegotiationSession] = {}

    def create(self, session: NegotiationSession) -> NegotiationSession:
        self._sessions[session.id] = session
        return session

    def get(self, session_id: UUID) -> NegotiationSession | None:
        return self._sessions.get(session_id)

    def get_for_update(self, session_id: UUID) -> NegotiationSession | None:
        return self.get(session_id)

    def list(self) -> list[NegotiationSession]:
        return list(self._sessions.values())

    def update(self, session: NegotiationSession) -> NegotiationSession:
        if session.id not in self._sessions:
            raise NegotiationSessionNotFoundError(session.id)

        self._sessions[session.id] = session
        return session
