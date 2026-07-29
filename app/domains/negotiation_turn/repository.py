from uuid import UUID

from app.domains.negotiation_turn.models import NegotiationTurn


class NegotiationTurnRepository:
    def __init__(self) -> None:
        self._turns: dict[UUID, NegotiationTurn] = {}

    def create(self, turn: NegotiationTurn) -> NegotiationTurn:
        self._turns[turn.id] = turn
        return turn

    def get(self, turn_id: UUID) -> NegotiationTurn | None:
        return self._turns.get(turn_id)

    def list_by_session(self, session_id: UUID) -> list[NegotiationTurn]:
        return sorted(
            (turn for turn in self._turns.values() if turn.session_id == session_id),
            key=lambda turn: turn.turn_number,
        )
