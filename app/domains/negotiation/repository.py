from uuid import UUID

from app.domains.negotiation.models import NegotiationSession
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError


class NegotiationRepository:
    def __init__(self) -> None:
        self._sessions: dict[UUID, NegotiationSession] = {}

    def create(self, session: NegotiationSession) -> NegotiationSession:
        self._sessions[session.id] = session
        return session

    def get_for_user(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationSession | None:
        session = self._sessions.get(session_id)
        if session is None or session.user_id != user_id:
            return None
        return session

    def get_for_update_for_user(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationSession | None:
        return self.get_for_user(session_id, user_id)

    def list_for_user(self, user_id: UUID) -> list[NegotiationSession]:
        return [
            session for session in self._sessions.values() if session.user_id == user_id
        ]

    def update_for_user(
        self,
        session: NegotiationSession,
        user_id: UUID,
    ) -> NegotiationSession:
        existing = self._sessions.get(session.id)
        if (
            existing is None
            or existing.user_id != user_id
            or session.user_id != user_id
        ):
            raise NegotiationSessionNotFoundError(session.id)

        self._sessions[session.id] = session
        return session
