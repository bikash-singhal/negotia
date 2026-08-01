from dataclasses import dataclass
from uuid import UUID

from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.memory.models import NegotiatorMemoryRecord
from app.domains.negotiation.models import NegotiationSession
from app.domains.negotiation_turn.models import NegotiationTurn
from app.domains.strategy.models import NegotiationStrategyRecord
from app.services.coach import CoachService
from app.services.opponent import OpponentService
from app.workflows.completion.service import CompletionWorkflowService


@dataclass(frozen=True)
class NegotiationCompletionResult:
    session: NegotiationSession
    debrief_record: NegotiationDebriefRecord
    strategy_record: NegotiationStrategyRecord
    memory_record: NegotiatorMemoryRecord | None


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
