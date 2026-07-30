from datetime import UTC, datetime
from inspect import signature
from unittest.mock import MagicMock
from uuid import uuid4

from app.domains.adaptive_context.models import AdaptiveContext
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.services.adaptive_context import AdaptiveContextService
from app.services.memory import MemoryService
from app.services.negotiation_engine import NegotiationEngine


def _create_memory_record(
    *,
    focus_area: str = "Diagnostic questioning",
) -> NegotiatorMemoryRecord:
    return NegotiatorMemoryRecord(
        id=uuid4(),
        trigger_session_id=uuid4(),
        memory=NegotiatorMemory(
            recurring_strengths=["Uses conditional concessions."],
            recurring_weaknesses=["Anchors before discovery."],
            improving_skills=["Active listening"],
            persistent_risks=["Makes unilateral concessions."],
            priority_focus_areas=[focus_area],
            recommended_drills=["Practice five discovery questions."],
            sessions_analyzed=2,
            confidence="medium",
        ),
        source_session_ids=(uuid4(), uuid4()),
        created_at=datetime.now(UTC),
    )


def test_get_context_returns_none_when_memory_is_absent() -> None:
    memory_service = MagicMock(spec=MemoryService)
    memory_service.get_latest.return_value = None
    service = AdaptiveContextService(memory_service)

    result = service.get_context()

    assert result is None
    memory_service.get_latest.assert_called_once_with()


def test_get_context_projects_only_confirmed_memory_fields() -> None:
    record = _create_memory_record()
    memory_service = MagicMock(spec=MemoryService)
    memory_service.get_latest.return_value = record
    service = AdaptiveContextService(memory_service)

    result = service.get_context()

    assert result == AdaptiveContext(
        focus_areas=["Diagnostic questioning"],
        coaching_focus=["Active listening"],
        opponent_adjustments=["Makes unilateral concessions."],
        strengths=["Uses conditional concessions."],
    )
    assert record.memory.recurring_weaknesses == ["Anchors before discovery."]
    assert record.memory.recommended_drills == ["Practice five discovery questions."]


def test_projection_defensively_copies_every_list() -> None:
    record = _create_memory_record()
    memory_service = MagicMock(spec=MemoryService)
    memory_service.get_latest.return_value = record
    service = AdaptiveContextService(memory_service)

    result = service.get_context()

    assert result is not None
    assert result.focus_areas is not record.memory.priority_focus_areas
    assert result.coaching_focus is not record.memory.improving_skills
    assert result.opponent_adjustments is not record.memory.persistent_risks
    assert result.strengths is not record.memory.recurring_strengths
    result.focus_areas.append("New runtime focus")
    assert record.memory.priority_focus_areas == ["Diagnostic questioning"]


def test_mapping_is_deterministic_without_caching() -> None:
    record = _create_memory_record()
    memory_service = MagicMock(spec=MemoryService)
    memory_service.get_latest.return_value = record
    service = AdaptiveContextService(memory_service)

    first = service.get_context()
    second = service.get_context()

    assert first == second
    assert first is not second
    assert first is not None
    assert second is not None
    assert first.focus_areas is not second.focus_areas
    assert memory_service.get_latest.call_count == 2


def test_each_call_reflects_latest_persisted_memory() -> None:
    first_record = _create_memory_record(focus_area="Diagnostic questioning")
    second_record = _create_memory_record(focus_area="Concession planning")
    memory_service = MagicMock(spec=MemoryService)
    memory_service.get_latest.side_effect = [first_record, second_record]
    service = AdaptiveContextService(memory_service)

    first = service.get_context()
    second = service.get_context()

    assert first is not None
    assert second is not None
    assert first.focus_areas == ["Diagnostic questioning"]
    assert second.focus_areas == ["Concession planning"]


def test_service_has_only_memory_service_dependency() -> None:
    parameters = signature(AdaptiveContextService.__init__).parameters

    assert list(parameters) == ["self", "memory_service"]


def test_negotiation_engine_has_no_adaptive_context_dependency() -> None:
    parameters = signature(NegotiationEngine.__init__).parameters

    assert "adaptive_context_service" not in parameters
