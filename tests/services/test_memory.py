import json
from datetime import UTC, datetime, timedelta
from inspect import signature
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.memory.exceptions import (
    DuplicateMemoryDebriefSessionError,
    DuplicateMemoryStrategySessionError,
    EmptyMemoryHistoryError,
    EmptyMemoryResponseError,
    InsufficientMemoryHistoryError,
    InvalidMemoryDataError,
    InvalidMemoryJsonError,
    MemorySessionsAnalyzedMismatchError,
    MismatchedMemoryArtifactSetError,
)
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.memory.repository import NegotiatorMemoryRepository
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
)
from app.domains.strategy.repository import NegotiationStrategyRepository
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider
from app.prompts.memory import MemoryPromptBuilder
from app.services.memory import MemoryExtractor, MemoryService


def _create_debrief_record(session_id: UUID) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=NegotiationDebrief(
            repeated_strengths=["Uses conditional concessions."],
            repeated_weaknesses=["Anchors before discovery."],
            key_missed_opportunities=["Did not test the deadline."],
            recurring_risks=["Makes unilateral concessions."],
            overall_assessment="Constructive but too quick to concede.",
            confidence="high",
        ),
        observation_count=2,
        created_at=datetime.now(UTC),
    )


def _create_strategy_record(
    session_id: UUID,
    debrief_id: UUID,
) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=debrief_id,
        strategy=NegotiationStrategy(
            primary_objective="Make concessions conditional.",
            expected_outcome="Receive reciprocal value.",
            prioritized_tactics=[],
            long_term_skills=["Concession planning"],
            preparation_checklist=["Define reciprocal asks."],
            avoid_next_time=["Avoid unilateral concessions."],
            confidence="high",
        ),
        created_at=datetime.now(UTC),
    )


def _valid_memory() -> NegotiatorMemory:
    return NegotiatorMemory(
        recurring_strengths=["Uses conditional concessions."],
        recurring_weaknesses=["Anchors before gathering information."],
        improving_skills=["Concession planning"],
        persistent_risks=["Makes unilateral concessions."],
        priority_focus_areas=["Diagnostic questioning"],
        recommended_drills=["Practice five discovery questions."],
        sessions_analyzed=2,
        confidence="medium",
    )


def _valid_payload(session_count: int = 2) -> dict[str, object]:
    return {
        "recurring_strengths": ["Uses conditional concessions."],
        "recurring_weaknesses": ["Anchors before gathering information."],
        "improving_skills": ["Concession planning"],
        "persistent_risks": ["Makes unilateral concessions."],
        "priority_focus_areas": ["Diagnostic questioning"],
        "recommended_drills": ["Practice five discovery questions."],
        "sessions_analyzed": session_count,
        "confidence": "medium",
    }


def _build_extractor(
    response: str,
) -> tuple[MemoryExtractor, MagicMock, MagicMock]:
    prompt_builder = MagicMock(spec=MemoryPromptBuilder)
    prompt_builder.build_system_prompt.return_value = "memory system prompt"
    prompt_builder.build_user_prompt.return_value = "memory user prompt"
    provider = MagicMock(spec=LLMProvider)
    provider.generate.return_value = response
    return (
        MemoryExtractor(prompt_builder, provider),
        prompt_builder,
        provider,
    )


def _create_matched_records(
    *session_ids: UUID,
) -> tuple[list[NegotiationDebriefRecord], list[NegotiationStrategyRecord]]:
    debriefs = [_create_debrief_record(session_id) for session_id in session_ids]
    strategies = [
        _create_strategy_record(debrief.session_id, debrief.id) for debrief in debriefs
    ]
    return debriefs, strategies


def test_extractor_parses_valid_json_and_sorts_inputs_by_session_id() -> None:
    first_session_id = UUID("00000000-0000-0000-0000-000000000001")
    second_session_id = UUID("00000000-0000-0000-0000-000000000002")
    debriefs, strategies = _create_matched_records(
        second_session_id,
        first_session_id,
    )
    extractor, prompt_builder, provider = _build_extractor(json.dumps(_valid_payload()))

    result = extractor.extract(debriefs, strategies)

    assert result == _valid_memory()
    prompt_builder.build_system_prompt.assert_called_once_with()
    ordered_debriefs, ordered_strategies = (
        prompt_builder.build_user_prompt.call_args.args
    )
    assert [record.session_id for record in ordered_debriefs] == [
        first_session_id,
        second_session_id,
    ]
    assert [record.session_id for record in ordered_strategies] == [
        first_session_id,
        second_session_id,
    ]
    provider.generate.assert_called_once_with(
        system_prompt="memory system prompt",
        user_prompt="memory user prompt",
    )


def test_fake_provider_returns_valid_memory_for_two_sessions() -> None:
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    extractor = MemoryExtractor(MemoryPromptBuilder(), FakeLLMProvider())

    memory = extractor.extract(debriefs, strategies)

    assert memory.sessions_analyzed == 2
    assert memory.confidence == "medium"


def test_extractor_rejects_empty_history_before_prompt_or_provider() -> None:
    extractor, prompt_builder, provider = _build_extractor(json.dumps(_valid_payload()))

    with pytest.raises(EmptyMemoryHistoryError):
        extractor.extract([], [])

    prompt_builder.build_system_prompt.assert_not_called()
    provider.generate.assert_not_called()


def test_extractor_rejects_empty_provider_response() -> None:
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    extractor, _, _ = _build_extractor("   ")

    with pytest.raises(EmptyMemoryResponseError):
        extractor.extract(debriefs, strategies)


def test_extractor_rejects_malformed_json_without_exposing_output() -> None:
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    extractor, _, _ = _build_extractor("not JSON with private artifact data")

    with pytest.raises(InvalidMemoryJsonError) as exc_info:
        extractor.extract(debriefs, strategies)

    assert "private artifact data" not in str(exc_info.value)


@pytest.mark.parametrize(
    "mutate_payload",
    [
        lambda payload: payload.pop("confidence"),
        lambda payload: payload.update({"unexpected": "value"}),
        lambda payload: payload.update({"sessions_analyzed": "2"}),
    ],
    ids=["missing-field", "extra-field", "non-strict-session-count"],
)
def test_extractor_rejects_invalid_memory_data(mutate_payload: object) -> None:
    assert callable(mutate_payload)
    payload = _valid_payload()
    mutate_payload(payload)
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    extractor, _, _ = _build_extractor(json.dumps(payload))

    with pytest.raises(InvalidMemoryDataError):
        extractor.extract(debriefs, strategies)


def test_extractor_rejects_duplicate_debrief_sessions() -> None:
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    extractor, _, provider = _build_extractor(json.dumps(_valid_payload()))

    with pytest.raises(DuplicateMemoryDebriefSessionError) as exc_info:
        extractor.extract([debriefs[0], debriefs[0], debriefs[1]], strategies)

    assert exc_info.value.session_id == debriefs[0].session_id
    provider.generate.assert_not_called()


def test_extractor_rejects_duplicate_strategy_sessions() -> None:
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    extractor, _, provider = _build_extractor(json.dumps(_valid_payload()))

    with pytest.raises(DuplicateMemoryStrategySessionError) as exc_info:
        extractor.extract(debriefs, [strategies[0], strategies[0], strategies[1]])

    assert exc_info.value.session_id == strategies[0].session_id
    provider.generate.assert_not_called()


def test_extractor_rejects_mismatched_session_sets() -> None:
    debriefs, _ = _create_matched_records(uuid4(), uuid4())
    _, strategies = _create_matched_records(uuid4(), uuid4())
    extractor, _, provider = _build_extractor(json.dumps(_valid_payload()))

    with pytest.raises(MismatchedMemoryArtifactSetError):
        extractor.extract(debriefs, strategies)

    provider.generate.assert_not_called()


def test_extractor_rejects_sessions_analyzed_mismatch() -> None:
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    extractor, _, _ = _build_extractor(json.dumps(_valid_payload(3)))

    with pytest.raises(MemorySessionsAnalyzedMismatchError) as exc_info:
        extractor.extract(debriefs, strategies)

    assert exc_info.value.expected == 2
    assert exc_info.value.actual == 3


def test_provider_failure_propagates_unchanged() -> None:
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    extractor, _, provider = _build_extractor(json.dumps(_valid_payload()))
    expected_error = RuntimeError("Provider failed")
    provider.generate.side_effect = expected_error

    with pytest.raises(RuntimeError) as exc_info:
        extractor.extract(debriefs, strategies)

    assert exc_info.value is expected_error


@pytest.mark.parametrize("session_count", [0, 1])
def test_service_rejects_insufficient_complete_history(
    session_count: int,
) -> None:
    session_ids = [uuid4() for _ in range(session_count)]
    debriefs, strategies = _create_matched_records(*session_ids)
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    debrief_repository.get_by_session.side_effect = lambda session_id: next(
        (record for record in debriefs if record.session_id == session_id),
        None,
    )
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    strategy_repository.list_all.return_value = strategies
    extractor = MagicMock(spec=MemoryExtractor)
    memory_repository = MagicMock(spec=NegotiatorMemoryRepository)
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    with pytest.raises(InsufficientMemoryHistoryError) as exc_info:
        service.generate()

    assert exc_info.value.session_count == session_count
    extractor.extract.assert_not_called()
    memory_repository.create.assert_not_called()


def test_service_rejects_mismatched_artifacts_before_history_count() -> None:
    session_ids = [uuid4(), uuid4()]
    debriefs, strategies = _create_matched_records(*session_ids)
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    debrief_repository.get_by_session.side_effect = [debriefs[0], None]
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    strategy_repository.list_all.return_value = strategies
    extractor = MagicMock(spec=MemoryExtractor)
    memory_repository = MagicMock(spec=NegotiatorMemoryRepository)
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    with pytest.raises(MismatchedMemoryArtifactSetError):
        service.generate()

    assert debrief_repository.get_by_session.call_count == 2
    extractor.extract.assert_not_called()
    memory_repository.create.assert_not_called()


def test_service_generates_and_persists_version_from_two_matched_sessions() -> None:
    first_session_id = UUID("00000000-0000-0000-0000-000000000001")
    second_session_id = UUID("00000000-0000-0000-0000-000000000002")
    debriefs, strategies = _create_matched_records(
        second_session_id,
        first_session_id,
    )
    debrief_repository = NegotiationDebriefRepository()
    strategy_repository = NegotiationStrategyRepository()
    for debrief in debriefs:
        debrief_repository.create(debrief)
    for strategy in strategies:
        strategy_repository.create(strategy)
    extractor = MagicMock(spec=MemoryExtractor)
    memory = _valid_memory()
    extractor.extract.return_value = memory
    memory_repository = NegotiatorMemoryRepository()
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    result = service.generate()

    assert isinstance(result, NegotiatorMemoryRecord)
    assert isinstance(result.id, UUID)
    assert result.trigger_session_id is None
    assert result.memory is memory
    assert result.source_session_ids == (
        first_session_id,
        second_session_id,
    )
    assert result.created_at.tzinfo is not None
    assert result.created_at.utcoffset() == timedelta(0)
    assert memory_repository.get_latest() is result
    assert memory_repository.list_all() == [result]
    extractor.extract.assert_called_once_with(debriefs, strategies)


def test_generate_for_session_returns_none_with_one_matched_session() -> None:
    trigger_session_id = uuid4()
    debriefs, strategies = _create_matched_records(trigger_session_id)
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    debrief_repository.get_by_session.return_value = debriefs[0]
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    strategy_repository.list_all.return_value = strategies
    extractor = MagicMock(spec=MemoryExtractor)
    memory_repository = MagicMock(spec=NegotiatorMemoryRepository)
    memory_repository.get_by_trigger_session.return_value = None
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    result = service.generate_for_session(trigger_session_id)

    assert result is None
    extractor.extract.assert_not_called()
    memory_repository.create.assert_not_called()


def test_generate_for_session_persists_completion_lineage() -> None:
    first_session_id = UUID("00000000-0000-0000-0000-000000000001")
    trigger_session_id = UUID("00000000-0000-0000-0000-000000000002")
    debriefs, strategies = _create_matched_records(
        trigger_session_id,
        first_session_id,
    )
    debrief_repository = NegotiationDebriefRepository()
    strategy_repository = NegotiationStrategyRepository()
    for debrief in debriefs:
        debrief_repository.create(debrief)
    for strategy in strategies:
        strategy_repository.create(strategy)
    extractor = MagicMock(spec=MemoryExtractor)
    extractor.extract.return_value = _valid_memory()
    memory_repository = NegotiatorMemoryRepository()
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    result = service.generate_for_session(trigger_session_id)

    assert result is not None
    assert result.trigger_session_id == trigger_session_id
    assert result.source_session_ids == (
        first_session_id,
        trigger_session_id,
    )
    assert memory_repository.get_by_trigger_session(trigger_session_id) is result
    assert result.created_at.utcoffset() == timedelta(0)


def test_prepare_for_session_builds_candidate_without_persisting() -> None:
    first_session_id = UUID("00000000-0000-0000-0000-000000000001")
    trigger_session_id = UUID("00000000-0000-0000-0000-000000000002")
    debriefs, strategies = _create_matched_records(
        trigger_session_id,
        first_session_id,
    )
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    debrief_repository.get_by_session.return_value = debriefs[0]
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    strategy_repository.list_all.return_value = [strategies[0]]
    extractor = MagicMock(spec=MemoryExtractor)
    extractor.extract.return_value = _valid_memory()
    memory_repository = MagicMock(spec=NegotiatorMemoryRepository)
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    result = service.prepare_for_session(
        trigger_session_id,
        debriefs[1],
        strategies[1],
    )

    assert result is not None
    assert result.trigger_session_id == trigger_session_id
    assert result.source_session_ids == (first_session_id, trigger_session_id)
    memory_repository.create.assert_not_called()


def test_generate_allows_multiple_standalone_versions_without_lineage() -> None:
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    debrief_repository = NegotiationDebriefRepository()
    strategy_repository = NegotiationStrategyRepository()
    for debrief in debriefs:
        debrief_repository.create(debrief)
    for strategy in strategies:
        strategy_repository.create(strategy)
    extractor = MagicMock(spec=MemoryExtractor)
    extractor.extract.return_value = _valid_memory()
    memory_repository = NegotiatorMemoryRepository()
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    first = service.generate()
    second = service.generate()

    assert first.trigger_session_id is None
    assert second.trigger_session_id is None
    assert first.id != second.id
    assert memory_repository.list_all() == [first, second]
    assert extractor.extract.call_count == 2


def test_generate_for_session_reuses_trigger_record_without_extraction() -> None:
    trigger_session_id = uuid4()
    expected_record = NegotiatorMemoryRecord(
        id=uuid4(),
        trigger_session_id=trigger_session_id,
        memory=_valid_memory(),
        source_session_ids=(uuid4(), trigger_session_id),
        created_at=datetime.now(UTC),
    )
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    extractor = MagicMock(spec=MemoryExtractor)
    memory_repository = MagicMock(spec=NegotiatorMemoryRepository)
    memory_repository.get_by_trigger_session.return_value = expected_record
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    result = service.generate_for_session(trigger_session_id)

    assert result is expected_record
    memory_repository.get_by_trigger_session.assert_called_once_with(trigger_session_id)
    strategy_repository.list_all.assert_not_called()
    debrief_repository.get_by_session.assert_not_called()
    extractor.extract.assert_not_called()
    memory_repository.create.assert_not_called()


def test_later_completion_creates_new_immutable_memory_version() -> None:
    first_session_id = UUID("00000000-0000-0000-0000-000000000001")
    second_session_id = UUID("00000000-0000-0000-0000-000000000002")
    third_session_id = UUID("00000000-0000-0000-0000-000000000003")
    debrief_repository = NegotiationDebriefRepository()
    strategy_repository = NegotiationStrategyRepository()
    memory_repository = NegotiatorMemoryRepository()
    extractor = MagicMock(spec=MemoryExtractor)
    extractor.extract.side_effect = [
        _valid_memory(),
        _valid_memory().model_copy(update={"sessions_analyzed": 3}),
    ]
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )
    for session_id in (first_session_id, second_session_id):
        debrief = _create_debrief_record(session_id)
        debrief_repository.create(debrief)
        strategy_repository.create(_create_strategy_record(session_id, debrief.id))

    second_memory = service.generate_for_session(second_session_id)
    third_debrief = _create_debrief_record(third_session_id)
    debrief_repository.create(third_debrief)
    strategy_repository.create(
        _create_strategy_record(third_session_id, third_debrief.id)
    )
    third_memory = service.generate_for_session(third_session_id)

    assert second_memory is not None
    assert third_memory is not None
    assert second_memory is not third_memory
    assert second_memory.source_session_ids == (
        first_session_id,
        second_session_id,
    )
    assert third_memory.source_session_ids == (
        first_session_id,
        second_session_id,
        third_session_id,
    )
    assert memory_repository.list_all() == [second_memory, third_memory]


def test_service_does_not_persist_when_extraction_fails() -> None:
    debriefs, strategies = _create_matched_records(uuid4(), uuid4())
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    debrief_repository.get_by_session.side_effect = debriefs
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    strategy_repository.list_all.return_value = strategies
    extractor = MagicMock(spec=MemoryExtractor)
    expected_error = InvalidMemoryDataError()
    extractor.extract.side_effect = expected_error
    memory_repository = MagicMock(spec=NegotiatorMemoryRepository)
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    with pytest.raises(InvalidMemoryDataError) as exc_info:
        service.generate()

    assert exc_info.value is expected_error
    memory_repository.create.assert_not_called()


def test_get_latest_and_list_versions_delegate_to_memory_repository() -> None:
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    extractor = MagicMock(spec=MemoryExtractor)
    memory_repository = MagicMock(spec=NegotiatorMemoryRepository)
    expected_record = NegotiatorMemoryRecord(
        id=uuid4(),
        trigger_session_id=None,
        memory=_valid_memory(),
        source_session_ids=(uuid4(), uuid4()),
        created_at=datetime.now(UTC),
    )
    memory_repository.get_latest.return_value = expected_record
    memory_repository.list_all.return_value = [expected_record]
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    assert service.get_latest() is expected_record
    assert service.list_versions() == [expected_record]
    memory_repository.get_latest.assert_called_once_with()
    memory_repository.list_all.assert_called_once_with()


def test_get_by_trigger_session_delegates_to_memory_repository() -> None:
    trigger_session_id = uuid4()
    expected_record = NegotiatorMemoryRecord(
        id=uuid4(),
        trigger_session_id=trigger_session_id,
        memory=_valid_memory(),
        source_session_ids=(uuid4(), trigger_session_id),
        created_at=datetime.now(UTC),
    )
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    extractor = MagicMock(spec=MemoryExtractor)
    memory_repository = MagicMock(spec=NegotiatorMemoryRepository)
    memory_repository.get_by_trigger_session.return_value = expected_record
    service = MemoryService(
        debrief_repository,
        strategy_repository,
        extractor,
        memory_repository,
    )

    result = service.get_by_trigger_session(trigger_session_id)

    assert result is expected_record
    memory_repository.get_by_trigger_session.assert_called_once_with(trigger_session_id)


def test_service_has_only_confirmed_dependencies() -> None:
    parameters = signature(MemoryService.__init__).parameters

    assert list(parameters) == [
        "self",
        "debrief_repository",
        "strategy_repository",
        "extractor",
        "memory_repository",
    ]
