from uuid import UUID

from app.domains.negotiation_turn.models import NegotiationTurn


class NegotiationTurnRepository:
    def __init__(self) -> None:
        self._turns: dict[UUID, NegotiationTurn] = {}
        self._user_ids: dict[UUID, UUID] = {}

    def create(self, turn: NegotiationTurn, user_id: UUID) -> NegotiationTurn:
        self._turns[turn.id] = turn
        self._user_ids[turn.id] = user_id
        return turn

    def get_for_user(self, turn_id: UUID, user_id: UUID) -> NegotiationTurn | None:
        if self._user_ids.get(turn_id) != user_id:
            return None
        return self._turns.get(turn_id)

    def list_by_session_for_user(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> list[NegotiationTurn]:
        return sorted(
            (
                turn
                for turn in self._turns.values()
                if turn.session_id == session_id
                and self._user_ids.get(turn.id) == user_id
            ),
            key=lambda turn: turn.turn_number,
        )
