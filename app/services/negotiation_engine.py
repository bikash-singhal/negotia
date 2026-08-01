from collections.abc import Iterator
from dataclasses import dataclass
from threading import Lock
from uuid import UUID

from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.memory.models import NegotiatorMemoryRecord
from app.domains.negotiation.models import NegotiationSession
from app.domains.negotiation_turn.models import NegotiationTurn
from app.domains.strategy.models import NegotiationStrategyRecord
from app.services.coach import CoachService
from app.services.opponent import (
    OpponentResponsePreparation,
    OpponentService,
)
from app.workflows.completion.service import CompletionWorkflowService


@dataclass(frozen=True)
class NegotiationCompletionResult:
    session: NegotiationSession
    debrief_record: NegotiationDebriefRecord
    strategy_record: NegotiationStrategyRecord
    memory_record: NegotiatorMemoryRecord | None


class NegotiationResponseStream:
    def __init__(
        self,
        opponent_service: OpponentService,
        coach_service: CoachService,
        preparation: OpponentResponsePreparation,
    ) -> None:
        self._opponent_service = opponent_service
        self._coach_service = coach_service
        self._preparation = preparation
        self._state_lock = Lock()
        self._stream_started = False
        self._completion_started = False
        self._closed = False

    def chunks(self) -> Iterator[str]:
        with self._state_lock:
            if self._stream_started or self._closed:
                raise RuntimeError("Opponent response stream is no longer available.")
            self._stream_started = True
        return self._opponent_service.stream_response(self._preparation)

    def complete(self, generated_content: str) -> NegotiationTurn:
        with self._state_lock:
            if self._closed or self._completion_started:
                raise RuntimeError("Opponent response stream is no longer available.")
            self._completion_started = True

        try:
            result = self._opponent_service.complete_streaming_response(
                self._preparation,
                generated_content,
            )
            self._coach_service.analyze_exchange(
                self._preparation.session_id,
                self._preparation.user_id,
                result.conversation_turns,
                result.user_turn,
                result.opponent_turn,
            )
            return result.opponent_turn
        finally:
            self.close()

    def close(self) -> None:
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
        self._opponent_service.cancel_streaming_response(self._preparation)


class NegotiationEngine:
    def __init__(
        self,
        opponent_service: OpponentService,
        coach_service: CoachService,
        completion_workflow_service: CompletionWorkflowService,
    ) -> None:
        self._opponent_service = opponent_service
        self._coach_service = coach_service
        self._completion_workflow_service = completion_workflow_service

    def generate_response(self, session_id: UUID, user_id: UUID) -> NegotiationTurn:
        result = self._opponent_service.generate_response(session_id, user_id)
        self._coach_service.analyze_exchange(
            session_id,
            user_id,
            result.conversation_turns,
            result.user_turn,
            result.opponent_turn,
        )
        return result.opponent_turn

    def start_response_stream(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationResponseStream:
        preparation = self._opponent_service.begin_streaming_response(
            session_id,
            user_id,
        )
        return NegotiationResponseStream(
            self._opponent_service,
            self._coach_service,
            preparation,
        )

    def complete_session(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationCompletionResult:
        workflow_result = self._completion_workflow_service.run(session_id, user_id)
        return NegotiationCompletionResult(
            workflow_result.session,
            workflow_result.debrief_record,
            workflow_result.strategy_record,
            workflow_result.memory_record,
        )
