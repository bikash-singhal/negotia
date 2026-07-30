from uuid import UUID

from app.domains.negotiation_turn.models import NegotiationTurn
from app.services.coach import CoachService
from app.services.opponent import OpponentService


class NegotiationEngine:
    def __init__(
        self,
        opponent_service: OpponentService,
        coach_service: CoachService,
    ) -> None:
        self._opponent_service = opponent_service
        self._coach_service = coach_service

    def generate_response(self, session_id: UUID) -> NegotiationTurn:
        result = self._opponent_service.generate_response(session_id)
        self._coach_service.analyze_exchange(
            session_id,
            result.conversation_turns,
            result.user_turn,
            result.opponent_turn,
        )
        return result.opponent_turn
