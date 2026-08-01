from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation_turn.exceptions import (
    NegotiationSessionNotFoundError,
)
from app.domains.negotiation_turn.models import NegotiationTurn
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.negotiation_turn.schemas import NegotiationTurnCreate


class NegotiationTurnService:
    def __init__(
        self,
        turn_repository: NegotiationTurnRepository,
        negotiation_repository: NegotiationRepository,
    ) -> None:
        self._turn_repository = turn_repository
        self._negotiation_repository = negotiation_repository

    def create_turn(
        self,
        request: NegotiationTurnCreate,
        user_id: UUID,
    ) -> NegotiationTurn:
        if (
            self._negotiation_repository.get_for_user(request.session_id, user_id)
            is None
        ):
            raise NegotiationSessionNotFoundError(request.session_id)

        existing_turns = self._turn_repository.list_by_session_for_user(
            request.session_id,
            user_id,
        )
        turn_number = existing_turns[-1].turn_number + 1 if existing_turns else 1
        turn = NegotiationTurn(
            id=uuid4(),
            session_id=request.session_id,
            speaker=request.speaker,
            content=request.content,
            turn_number=turn_number,
            created_at=datetime.now(UTC),
        )

        return self._turn_repository.create(turn, user_id)

    def get_turn(self, turn_id: UUID, user_id: UUID) -> NegotiationTurn | None:
        return self._turn_repository.get_for_user(turn_id, user_id)

    def list_turns(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> list[NegotiationTurn]:
        if self._negotiation_repository.get_for_user(session_id, user_id) is None:
            raise NegotiationSessionNotFoundError(session_id)

        return self._turn_repository.list_by_session_for_user(session_id, user_id)
