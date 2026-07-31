import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.database.unit_of_work import CompletionUnitOfWork
from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.domains.negotiation.exceptions import CompletionArtifactsChangedError
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


def test_service_retries_artifact_change_once_and_logs_exactly_once() -> None:
    session_id = uuid4()
    final_state, expected_result = _create_final_state(session_id)
    graph = MagicMock()
    graph.invoke.side_effect = [
        CompletionArtifactsChangedError(session_id),
        final_state,
    ]
    records: list[logging.LogRecord] = []

    class RecordHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    workflow_logger = logging.getLogger("app.workflows.completion.service")
    handler = RecordHandler()
    previous_level = workflow_logger.level
    previous_disabled = workflow_logger.disabled
    workflow_logger.disabled = False
    workflow_logger.setLevel(logging.WARNING)
    workflow_logger.addHandler(handler)

    with patch(
        "app.workflows.completion.service.build_completion_graph",
        return_value=graph,
    ):
        service = _build_service()

    try:
        result = service.run(session_id)
    finally:
        workflow_logger.removeHandler(handler)
        workflow_logger.setLevel(previous_level)
        workflow_logger.disabled = previous_disabled

    retry_records = [
        record
        for record in records
        if getattr(record, "event", None) == "completion_retry_due_to_artifact_change"
    ]
    assert len(retry_records) == 1
    assert getattr(retry_records[0], "session_id", None) == str(session_id)
    assert result == expected_result
    assert graph.invoke.call_count == 2
    first_state = graph.invoke.call_args_list[0].args[0]
    second_state = graph.invoke.call_args_list[1].args[0]
    assert first_state == CompletionWorkflowState(session_id=session_id)
    assert second_state == CompletionWorkflowState(session_id=session_id)
    assert first_state is not second_state


def test_service_propagates_second_artifact_change_after_exactly_one_retry() -> None:
    session_id = uuid4()
    first_error = CompletionArtifactsChangedError(session_id)
    second_error = CompletionArtifactsChangedError(session_id)
    graph = MagicMock()
    graph.invoke.side_effect = [first_error, second_error]

    with patch(
        "app.workflows.completion.service.build_completion_graph",
        return_value=graph,
    ):
        service = _build_service()

    with pytest.raises(CompletionArtifactsChangedError) as exc_info:
        service.run(session_id)

    assert exc_info.value is second_error
    assert graph.invoke.call_count == 2


def test_service_does_not_retry_unrelated_errors() -> None:
    session_id = uuid4()
    expected_error = RuntimeError("workflow failed")
    graph = MagicMock()
    graph.invoke.side_effect = expected_error

    with patch(
        "app.workflows.completion.service.build_completion_graph",
        return_value=graph,
    ):
        service = _build_service()

    with pytest.raises(RuntimeError) as exc_info:
        service.run(session_id)

    assert exc_info.value is expected_error
    graph.invoke.assert_called_once_with(CompletionWorkflowState(session_id=session_id))
