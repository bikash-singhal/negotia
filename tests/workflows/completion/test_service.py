from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.database.unit_of_work import CompletionUnitOfWork
from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
)
from app.services.debrief import DebriefService
from app.services.memory import MemoryService
from app.services.strategy import StrategyService
from app.workflows.completion.service import CompletionWorkflowService
from app.workflows.completion.state import (
    CompletionWorkflowResult,
    CompletionWorkflowState,
)


def _create_final_state(
    session_id: UUID,
) -> tuple[CompletionWorkflowState, CompletionWorkflowResult]:
    now = datetime.now(UTC)
    session = NegotiationSession(
        id=session_id,
        scenario_id=uuid4(),
        status=NegotiationStatus.COMPLETED,
        created_at=now,
        updated_at=now,
    )
    debrief = NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=NegotiationDebrief(
            repeated_strengths=[],
            repeated_weaknesses=[],
            key_missed_opportunities=[],
            recurring_risks=[],
            overall_assessment="A concise assessment.",
            confidence="low",
        ),
        observation_count=1,
        created_at=now,
    )
    strategy = NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=debrief.id,
        strategy=NegotiationStrategy(
            primary_objective="Prepare conditional trades.",
            expected_outcome="Concessions receive reciprocal value.",
            prioritized_tactics=[],
            long_term_skills=[],
            preparation_checklist=[],
            avoid_next_time=[],
            confidence="low",
        ),
        created_at=now,
    )
    state = CompletionWorkflowState(
        session_id=session_id,
        session=session,
        debrief_record=debrief,
        strategy_record=strategy,
        memory_record=None,
    )
    return state, CompletionWorkflowResult(session, debrief, strategy, None)


def _build_service() -> CompletionWorkflowService:
    return CompletionWorkflowService(
        MagicMock(spec=NegotiationService),
        MagicMock(spec=NegotiationTurnService),
        MagicMock(spec=DebriefService),
        MagicMock(spec=StrategyService),
        MagicMock(spec=MemoryService),
        MagicMock(return_value=MagicMock(spec=CompletionUnitOfWork)),
    )


def test_service_compiles_once_invokes_once_and_returns_typed_result() -> None:
    session_id = uuid4()
    final_state, expected_result = _create_final_state(session_id)
    graph = MagicMock()
    graph.invoke.return_value = final_state

    with patch(
        "app.workflows.completion.service.build_completion_graph",
        return_value=graph,
    ) as build_graph:
        service = _build_service()
        result = service.run(session_id)

    assert result == expected_result
    build_graph.assert_called_once_with(service._nodes)
    graph.invoke.assert_called_once_with(CompletionWorkflowState(session_id=session_id))


def test_service_does_not_recompile_between_runs() -> None:
    session_id = uuid4()
    final_state, _ = _create_final_state(session_id)
    graph = MagicMock()
    graph.invoke.return_value = final_state

    with patch(
        "app.workflows.completion.service.build_completion_graph",
        return_value=graph,
    ) as build_graph:
        service = _build_service()
        service.run(session_id)
        service.run(session_id)

    build_graph.assert_called_once_with(service._nodes)
    assert graph.invoke.call_count == 2


def test_service_rejects_incomplete_final_state() -> None:
    session_id = uuid4()
    graph = MagicMock()
    graph.invoke.return_value = CompletionWorkflowState(session_id=session_id)

    with patch(
        "app.workflows.completion.service.build_completion_graph",
        return_value=graph,
    ):
        service = _build_service()

    with pytest.raises(RuntimeError, match="incomplete state"):
        service.run(session_id)
