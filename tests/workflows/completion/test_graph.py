from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.database.unit_of_work import CompletionUnitOfWork
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
from tests.ownership import TEST_USER_ID


def _create_session(
    status: NegotiationStatus = NegotiationStatus.CREATED,
) -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        user_id=TEST_USER_ID,
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
        user_id=TEST_USER_ID,
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
    services = (
        MagicMock(spec=NegotiationService),
        MagicMock(spec=NegotiationTurnService),
        MagicMock(spec=DebriefService),
        MagicMock(spec=StrategyService),
        MagicMock(spec=MemoryService),
    )
    services[2].get_for_session.return_value = None
    services[3].get_for_session.return_value = None
    services[4].get_by_trigger_session.return_value = None
    return services


def _build_unit_of_work_factory(
    session: NegotiationSession,
    debrief_service: MagicMock,
    strategy_service: MagicMock,
    memory_service: MagicMock,
) -> MagicMock:
    unit_of_work = MagicMock(spec=CompletionUnitOfWork)
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.negotiation_repository.get_for_update_for_user.return_value = session
    unit_of_work.negotiation_repository.update_for_user.side_effect = (
        lambda record, user_id: record
    )
    unit_of_work.debrief_repository.get_by_session_for_user.side_effect = (
        lambda _session_id, _user_id: debrief_service.get_for_session.return_value
    )
    unit_of_work.debrief_repository.create.side_effect = lambda record, user_id: record
    unit_of_work.strategy_repository.get_by_session_for_user.side_effect = (
        lambda _session_id, _user_id: strategy_service.get_for_session.return_value
    )
    unit_of_work.strategy_repository.create.side_effect = lambda record, user_id: record
    unit_of_work.memory_repository.get_by_trigger_session.side_effect = (
        lambda _session_id, _user_id: memory_service.get_by_trigger_session.return_value
    )
    unit_of_work.memory_repository.create.side_effect = lambda record: record
    return MagicMock(return_value=unit_of_work)


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
        lambda _session_id, _user_id: call_order.append("validate") or session
    )
    turn_service.list_turns.side_effect = lambda _session_id, _user_id: (
        call_order.append("turns") or turns
    )
    debrief_service.get_for_session.side_effect = lambda _session_id, _user_id: (
        call_order.append("debrief lookup") or None
    )
    debrief_service.prepare_for_session.side_effect = lambda _session_id, _user_id: (
        call_order.append("debrief create") or debrief
    )
    strategy_service.get_for_session.side_effect = lambda _session_id, _user_id: (
        call_order.append("strategy lookup") or None
    )
    strategy_service.prepare_for_session.side_effect = (
        lambda _session_id, _user_id, _debrief: (
            call_order.append("strategy create") or strategy
        )
    )
    memory_service.prepare_for_session.side_effect = (
        lambda _session_id, _user_id, _debrief, _strategy: (
            call_order.append("memory") or memory
        )
    )

    def mark_completed(_session_id: UUID) -> NegotiationSession:
        call_order.append("mark completed")
        session.status = NegotiationStatus.COMPLETED
        return session

    negotiation_service.prepare_completion.side_effect = lambda candidate: (
        mark_completed(candidate.id)
    )
    unit_of_work_factory = _build_unit_of_work_factory(
        session,
        debrief_service,
        strategy_service,
        memory_service,
    )
    unit_of_work = unit_of_work_factory.return_value
    unit_of_work_factory.side_effect = lambda: (
        call_order.append("unit of work open") or unit_of_work
    )
    unit_of_work.debrief_repository.create.side_effect = lambda record, user_id: (
        call_order.append("persist debrief") or record
    )
    unit_of_work.strategy_repository.create.side_effect = lambda record, user_id: (
        call_order.append("persist strategy") or record
    )
    unit_of_work.memory_repository.create.side_effect = lambda record: (
        call_order.append("persist memory") or record
    )
    unit_of_work.negotiation_repository.update_for_user.side_effect = (
        lambda record, user_id: call_order.append("persist completion") or record
    )
    unit_of_work.commit.side_effect = lambda: call_order.append("commit")
    graph = build_completion_graph(
        CompletionWorkflowNodes(
            negotiation_service,
            turn_service,
            debrief_service,
            strategy_service,
            memory_service,
            unit_of_work_factory,
        )
    )

    result = graph.invoke(
        CompletionWorkflowState(session_id=session.id, user_id=TEST_USER_ID)
    )

    assert call_order == [
        "validate",
        "turns",
        "debrief lookup",
        "debrief create",
        "strategy lookup",
        "strategy create",
        "memory",
        "unit of work open",
        "persist debrief",
        "persist strategy",
        "persist memory",
        "mark completed",
        "persist completion",
        "commit",
    ]
    unit_of_work.negotiation_repository.get_for_update_for_user.assert_called_once_with(
        session.id,
        TEST_USER_ID,
    )
    unit_of_work.negotiation_repository.update_for_user.assert_called_once_with(
        session,
        TEST_USER_ID,
    )
    unit_of_work.commit.assert_called_once_with()
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

    def debrief_result(
        _session_id: UUID,
        _user_id: UUID,
    ) -> NegotiationDebriefRecord:
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

    debrief_service.prepare_for_session.side_effect = debrief_result
    strategy_service.prepare_for_session.side_effect = (
        lambda session_id, _user_id, _debrief: strategy_result(session_id)
    )
    memory_service.prepare_for_session.side_effect = (
        lambda session_id, _user_id, _debrief, _strategy: memory_result(session_id)
    )
    negotiation_service.prepare_completion.side_effect = lambda candidate: (
        call_order.append("mark completed") or session
    )
    unit_of_work_factory = _build_unit_of_work_factory(
        session,
        debrief_service,
        strategy_service,
        memory_service,
    )
    graph = build_completion_graph(
        CompletionWorkflowNodes(
            negotiation_service,
            turn_service,
            debrief_service,
            strategy_service,
            memory_service,
            unit_of_work_factory,
        )
    )

    with pytest.raises(RuntimeError) as exc_info:
        graph.invoke(
            CompletionWorkflowState(session_id=session.id, user_id=TEST_USER_ID)
        )

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
    unit_of_work_factory = _build_unit_of_work_factory(
        session,
        debrief_service,
        strategy_service,
        memory_service,
    )
    graph = build_completion_graph(
        CompletionWorkflowNodes(
            negotiation_service,
            turn_service,
            debrief_service,
            strategy_service,
            memory_service,
            unit_of_work_factory,
        )
    )

    first = graph.invoke(
        CompletionWorkflowState(session_id=session.id, user_id=TEST_USER_ID)
    )
    second = graph.invoke(
        CompletionWorkflowState(session_id=session.id, user_id=TEST_USER_ID)
    )

    assert first == second
    assert first["session"] is session
    assert first["debrief_record"] is debrief
    assert first["strategy_record"] is strategy
    assert first["memory_record"] is memory
    assert session.updated_at is original_updated_at
    unit_of_work_factory.return_value.commit.assert_not_called()
    turn_service.list_turns.assert_not_called()
    debrief_service.prepare_for_session.assert_not_called()
    strategy_service.prepare_for_session.assert_not_called()
    memory_service.prepare_for_session.assert_not_called()
    negotiation_service.prepare_completion.assert_not_called()
