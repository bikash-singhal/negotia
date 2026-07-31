from itertools import pairwise
from uuid import UUID

from app.domains.negotiation.exceptions import (
    CompletedNegotiationMissingDebriefError,
    CompletedNegotiationMissingStrategyError,
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
from app.services.debrief import DebriefService
from app.services.memory import MemoryService
from app.services.strategy import StrategyService
from app.workflows.completion.state import (
    CompletionWorkflowState,
    CompletionWorkflowUpdate,
)


class CompletionWorkflowNodes:
    def __init__(
        self,
        negotiation_service: NegotiationService,
        negotiation_turn_service: NegotiationTurnService,
        debrief_service: DebriefService,
        strategy_service: StrategyService,
        memory_service: MemoryService,
    ) -> None:
        self._negotiation_service = negotiation_service
        self._negotiation_turn_service = negotiation_turn_service
        self._debrief_service = debrief_service
        self._strategy_service = strategy_service
        self._memory_service = memory_service

    def validate_session(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session_id = state["session_id"]
        session = self._negotiation_service.validate_completion_transition(session_id)
        if session.status is not NegotiationStatus.COMPLETED:
            turns = self._negotiation_turn_service.list_turns(session_id)
            self._validate_completion_turns(session_id, turns)

        return {"session": session}

    def create_or_reuse_debrief(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session = self._get_session(state)
        record = self._debrief_service.get_for_session(session.id)
        if record is None:
            if session.status is NegotiationStatus.COMPLETED:
                raise CompletedNegotiationMissingDebriefError(session.id)
            record = self._debrief_service.generate_for_session(session.id)

        return {"debrief_record": record}

    def create_or_reuse_strategy(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session = self._get_session(state)
        record = self._strategy_service.get_for_session(session.id)
        if record is None:
            if session.status is NegotiationStatus.COMPLETED:
                raise CompletedNegotiationMissingStrategyError(session.id)
            record = self._strategy_service.generate_for_session(session.id)

        return {"strategy_record": record}

    def create_or_reuse_memory(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session = self._get_session(state)
        if session.status is NegotiationStatus.COMPLETED:
            record = self._memory_service.get_by_trigger_session(session.id)
        else:
            record = self._memory_service.generate_for_session(session.id)

        return {"memory_record": record}

    def mark_completed(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session = self._get_session(state)
        if session.status is NegotiationStatus.COMPLETED:
            return {"session": session}

        return {"session": self._negotiation_service.mark_completed(session.id)}

    @staticmethod
    def _get_session(state: CompletionWorkflowState) -> NegotiationSession:
        if "session" not in state:
            raise RuntimeError("Completion workflow session state is unavailable.")
        return state["session"]

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
