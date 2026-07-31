from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
)
from app.services.debrief import DebriefService
from app.services.memory import MemoryService
from app.services.strategy import StrategyService
from app.workflows.completion.graph import build_completion_graph
from app.workflows.completion.nodes import CompletionWorkflowNodes
from app.workflows.completion.state import CompletionWorkflowState


def _create_session(
    status: NegotiationStatus = NegotiationStatus.CREATED,
) -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        scenario_id=uuid4(),
        status=status,
        created_at=now,
        updated_at=now,
    )


def _create_turn(
    session_id: UUID,
    turn_number: int,
    speaker: NegotiationTurnSpeaker,
) -> NegotiationTurn:
    return NegotiationTurn(
        id=uuid4(),
        session_id=session_id,
        speaker=speaker,
        content="Negotiation turn.",
        turn_number=turn_number,
        created_at=datetime.now(UTC),
    )


def _create_debrief(session_id: UUID) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
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
        created_at=datetime.now(UTC),
    )


def _create_strategy(
    session_id: UUID,
    debrief_id: UUID,
) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=debrief_id,
        strategy=NegotiationStrategy(
            primary_objective="Prepare conditional trades.",
            expected_outcome="Concessions receive reciprocal value.",
            prioritized_tactics=[],
            long_term_skills=[],
            preparation_checklist=[],
            avoid_next_time=[],
            confidence="low",
        ),
        created_at=datetime.now(UTC),
    )


def _create_memory(session_id: UUID) -> NegotiatorMemoryRecord:
    return NegotiatorMemoryRecord(
        id=uuid4(),
        trigger_session_id=session_id,
        memory=NegotiatorMemory(
            recurring_strengths=[],
            recurring_weaknesses=[],
            improving_skills=[],
            persistent_risks=[],
            priority_focus_areas=[],
            recommended_drills=[],
            sessions_analyzed=2,
            confidence="low",
        ),
        source_session_ids=(uuid4(), session_id),
        created_at=datetime.now(UTC),
    )


def _build_services() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    return (
        MagicMock(spec=NegotiationService),
        MagicMock(spec=NegotiationTurnService),
        MagicMock(spec=DebriefService),
        MagicMock(spec=StrategyService),
        MagicMock(spec=MemoryService),
    )


def test_graph_executes_linear_completion_order() -> None:
    session = _create_session()
    turns = [
        _create_turn(session.id, 1, NegotiationTurnSpeaker.USER),
        _create_turn(session.id, 2, NegotiationTurnSpeaker.OPPONENT),
    ]
    debrief = _create_debrief(session.id)
    strategy = _create_strategy(session.id, debrief.id)
    memory = _create_memory(session.id)
    (
        negotiation_service,
        turn_service,
        debrief_service,
        strategy_service,
        memory_service,
    ) = _build_services()
    call_order: list[str] = []
    negotiation_service.validate_completion_transition.side_effect = (
        lambda _session_id: call_order.append("validate") or session
    )
    turn_service.list_turns.side_effect = lambda _session_id: (
        call_order.append("turns") or turns
    )
    debrief_service.get_for_session.side_effect = lambda _session_id: (
        call_order.append("debrief lookup") or None
    )
    debrief_service.generate_for_session.side_effect = lambda _session_id: (
        call_order.append("debrief create") or debrief
    )
    strategy_service.get_for_session.side_effect = lambda _session_id: (
        call_order.append("strategy lookup") or None
    )
    strategy_service.generate_for_session.side_effect = lambda _session_id: (
        call_order.append("strategy create") or strategy
    )
    memory_service.generate_for_session.side_effect = lambda _session_id: (
        call_order.append("memory") or memory
    )

    def mark_completed(_session_id: UUID) -> NegotiationSession:
        call_order.append("mark completed")
        session.status = NegotiationStatus.COMPLETED
        return session

    negotiation_service.mark_completed.side_effect = mark_completed
    graph = build_completion_graph(
        CompletionWorkflowNodes(
            negotiation_service,
            turn_service,
            debrief_service,
            strategy_service,
            memory_service,
        )
    )

    result = graph.invoke(CompletionWorkflowState(session_id=session.id))

    assert call_order == [
        "validate",
        "turns",
        "debrief lookup",
        "debrief create",
        "strategy lookup",
        "strategy create",
        "memory",
        "mark completed",
    ]
    assert result["session"] is session
    assert result["debrief_record"] is debrief
    assert result["strategy_record"] is strategy
    assert result["memory_record"] is memory


@pytest.mark.parametrize(
    ("failing_stage", "forbidden_calls"),
    [
        ("debrief", ["strategy", "memory", "mark completed"]),
        ("strategy", ["memory", "mark completed"]),
        ("memory", ["mark completed"]),
    ],
)
def test_graph_stops_after_failure(
    failing_stage: str,
    forbidden_calls: list[str],
) -> None:
    session = _create_session()
    turns = [
        _create_turn(session.id, 1, NegotiationTurnSpeaker.USER),
        _create_turn(session.id, 2, NegotiationTurnSpeaker.OPPONENT),
    ]
    debrief = _create_debrief(session.id)
    strategy = _create_strategy(session.id, debrief.id)
    (
        negotiation_service,
        turn_service,
        debrief_service,
        strategy_service,
        memory_service,
    ) = _build_services()
    negotiation_service.validate_completion_transition.return_value = session
    turn_service.list_turns.return_value = turns
    debrief_service.get_for_session.return_value = None
    strategy_service.get_for_session.return_value = None
    expected_error = RuntimeError(f"{failing_stage} failed")
    call_order: list[str] = []

    def debrief_result(_session_id: UUID) -> NegotiationDebriefRecord:
        call_order.append("debrief")
        if failing_stage == "debrief":
            raise expected_error
        return debrief

    def strategy_result(_session_id: UUID) -> NegotiationStrategyRecord:
        call_order.append("strategy")
        if failing_stage == "strategy":
            raise expected_error
        return strategy

    def memory_result(_session_id: UUID) -> NegotiatorMemoryRecord:
        call_order.append("memory")
        if failing_stage == "memory":
            raise expected_error
        return _create_memory(session.id)

    debrief_service.generate_for_session.side_effect = debrief_result
    strategy_service.generate_for_session.side_effect = strategy_result
    memory_service.generate_for_session.side_effect = memory_result
    negotiation_service.mark_completed.side_effect = lambda _session_id: (
        call_order.append("mark completed") or session
    )
    graph = build_completion_graph(
        CompletionWorkflowNodes(
            negotiation_service,
            turn_service,
            debrief_service,
            strategy_service,
            memory_service,
        )
    )

    with pytest.raises(RuntimeError) as exc_info:
        graph.invoke(CompletionWorkflowState(session_id=session.id))

    assert exc_info.value is expected_error
    assert all(call not in call_order for call in forbidden_calls)


def test_completed_session_reuses_artifacts_without_validation_or_marking() -> None:
    session = _create_session(NegotiationStatus.COMPLETED)
    original_updated_at = session.updated_at
    debrief = _create_debrief(session.id)
    strategy = _create_strategy(session.id, debrief.id)
    memory = _create_memory(session.id)
    (
        negotiation_service,
        turn_service,
        debrief_service,
        strategy_service,
        memory_service,
    ) = _build_services()
    negotiation_service.validate_completion_transition.return_value = session
    debrief_service.get_for_session.return_value = debrief
    strategy_service.get_for_session.return_value = strategy
    memory_service.get_by_trigger_session.return_value = memory
    graph = build_completion_graph(
        CompletionWorkflowNodes(
            negotiation_service,
            turn_service,
            debrief_service,
            strategy_service,
            memory_service,
        )
    )

    first = graph.invoke(CompletionWorkflowState(session_id=session.id))
    second = graph.invoke(CompletionWorkflowState(session_id=session.id))

    assert first == second
    assert first["session"] is session
    assert first["debrief_record"] is debrief
    assert first["strategy_record"] is strategy
    assert first["memory_record"] is memory
    assert session.updated_at is original_updated_at
    turn_service.list_turns.assert_not_called()
    debrief_service.generate_for_session.assert_not_called()
    strategy_service.generate_for_session.assert_not_called()
    memory_service.generate_for_session.assert_not_called()
    negotiation_service.mark_completed.assert_not_called()
