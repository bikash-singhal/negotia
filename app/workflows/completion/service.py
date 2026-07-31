from uuid import UUID

from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.services.debrief import DebriefService
from app.services.memory import MemoryService
from app.services.strategy import StrategyService
from app.workflows.completion.graph import CompletionGraph, build_completion_graph
from app.workflows.completion.nodes import CompletionWorkflowNodes
from app.workflows.completion.state import (
    CompletionWorkflowResult,
    CompletionWorkflowState,
)


class CompletionWorkflowService:
    def __init__(
        self,
        negotiation_service: NegotiationService,
        negotiation_turn_service: NegotiationTurnService,
        debrief_service: DebriefService,
        strategy_service: StrategyService,
        memory_service: MemoryService,
    ) -> None:
        self._nodes = CompletionWorkflowNodes(
            negotiation_service,
            negotiation_turn_service,
            debrief_service,
            strategy_service,
            memory_service,
        )
        self._graph: CompletionGraph = build_completion_graph(self._nodes)

    def run(self, session_id: UUID) -> CompletionWorkflowResult:
        final_state = self._graph.invoke(CompletionWorkflowState(session_id=session_id))
        required_fields = {
            "session",
            "debrief_record",
            "strategy_record",
            "memory_record",
        }
        if not required_fields.issubset(final_state):
            raise RuntimeError("Completion workflow returned incomplete state.")

        return CompletionWorkflowResult(
            session=final_state["session"],
            debrief_record=final_state["debrief_record"],
            strategy_record=final_state["strategy_record"],
            memory_record=final_state["memory_record"],
        )
