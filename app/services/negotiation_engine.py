from dataclasses import dataclass
from itertools import pairwise
from uuid import UUID

from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.negotiation.exceptions import (
    CompletedNegotiationMissingDebriefError,
    NegotiationCompletionLatestTurnFromUserError,
    NegotiationCompletionRequiresExchangeError,
    NegotiationCompletionWithoutTurnsError,
)
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.services.coach import CoachService
from app.services.debrief import DebriefService
from app.services.opponent import OpponentService


@dataclass(frozen=True)
class NegotiationCompletionResult:
    session: NegotiationSession
    debrief_record: NegotiationDebriefRecord


class NegotiationEngine:
    def __init__(
        self,
        opponent_service: OpponentService,
        coach_service: CoachService,
        negotiation_service: NegotiationService,
        negotiation_turn_service: NegotiationTurnService,
        debrief_service: DebriefService,
    ) -> None:
        self._opponent_service = opponent_service
        self._coach_service = coach_service
        self._negotiation_service = negotiation_service
        self._negotiation_turn_service = negotiation_turn_service
        self._debrief_service = debrief_service

    def generate_response(self, session_id: UUID) -> NegotiationTurn:
        result = self._opponent_service.generate_response(session_id)
        self._coach_service.analyze_exchange(
            session_id,
            result.conversation_turns,
            result.user_turn,
            result.opponent_turn,
        )
        return result.opponent_turn

    def complete_session(
        self,
        session_id: UUID,
    ) -> NegotiationCompletionResult:
        session = self._negotiation_service.validate_completion_transition(session_id)
        if session.status is NegotiationStatus.COMPLETED:
            existing_debrief = self._debrief_service.get_for_session(session_id)
            if existing_debrief is None:
                raise CompletedNegotiationMissingDebriefError(session_id)
            return NegotiationCompletionResult(session, existing_debrief)

        turns = self._negotiation_turn_service.list_turns(session_id)
        self._validate_completion_turns(session_id, turns)

        debrief_record = self._debrief_service.get_for_session(session_id)
        if debrief_record is None:
            debrief_record = self._debrief_service.generate_for_session(session_id)

        completed_session = self._negotiation_service.mark_completed(session_id)
        return NegotiationCompletionResult(completed_session, debrief_record)

    @staticmethod
    def _validate_completion_turns(
        session_id: UUID,
        turns: list[NegotiationTurn],
    ) -> None:
        if not turns:
            raise NegotiationCompletionWithoutTurnsError(session_id)

        if turns[-1].speaker is NegotiationTurnSpeaker.USER:
            raise NegotiationCompletionLatestTurnFromUserError(session_id)

        has_completed_exchange = any(
            first.speaker is NegotiationTurnSpeaker.USER
            and second.speaker is NegotiationTurnSpeaker.OPPONENT
            for first, second in pairwise(turns)
        )
        if not has_completed_exchange:
            raise NegotiationCompletionRequiresExchangeError(session_id)
