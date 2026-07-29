from uuid import UUID

from app.domains.negotiation.models import NegotiationSession


class NegotiationRepository:
    def __init__(self) -> None:
        self._sessions: dict[UUID, NegotiationSession] = {}

    def create(self, session: NegotiationSession) -> NegotiationSession:
        self._sessions[session.id] = session
        return session

    def get(self, session_id: UUID) -> NegotiationSession | None:
        return self._sessions.get(session_id)

    def list(self) -> list[NegotiationSession]:
        return list(self._sessions.values())
