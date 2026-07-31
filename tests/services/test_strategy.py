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
from app.domains.strategy.exceptions import (
    EmptyStrategyResponseError,
    InvalidStrategyDataError,
    InvalidStrategyJsonError,
    NegotiationDebriefNotFoundError,
    NegotiationStrategyAlreadyExistsError,
)
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
    NegotiationTactic,
)
from app.domains.strategy.repository import NegotiationStrategyRepository
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider
from app.prompts.strategy import StrategyPromptBuilder
from app.services.strategy import StrategyExtractor, StrategyService


def _create_debrief_record(
    session_id: UUID | None = None,
) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id or uuid4(),
        debrief=NegotiationDebrief(
            repeated_strengths=["Used conditional trades."],
            repeated_weaknesses=["Anchored before gathering information."],
            key_missed_opportunities=["Did not test the deadline."],
            recurring_risks=["Made unilateral concessions."],
            overall_assessment="Constructive but too quick to concede.",
            confidence="high",
        ),
        observation_count=3,
        created_at=datetime.now(UTC),
    )


def _valid_strategy() -> NegotiationStrategy:
    return NegotiationStrategy(
        primary_objective="Make every concession conditional.",
        expected_outcome="Every concession receives reciprocal value.",
        prioritized_tactics=[
            NegotiationTactic(
                priority=1,
                title="Trade rather than concede",
                rationale="Conditional trades protect value.",
                actions=["Request reciprocal value."],
                example_language=["I can agree if payment terms improve."],
                success_indicator="Every concession receives reciprocal value.",
            ),
            NegotiationTactic(
                priority=2,
                title="Prepare concession boundaries",
                rationale="Defined boundaries prevent reactive movement.",
                actions=["Set limits before negotiating."],
                example_language=["That is the furthest I can move on price."],
                success_indicator="No unplanned concessions are made.",
            ),
        ],
        long_term_skills=["Concession planning"],
        preparation_checklist=["Define reciprocal asks."],
        avoid_next_time=["Do not concede without receiving value."],
        confidence="high",
    )


def _valid_payload() -> dict[str, object]:
    return {
        "primary_objective": "Make every concession conditional.",
        "expected_outcome": "Every concession receives reciprocal value.",
        "prioritized_tactics": [
            {
                "priority": 2,
                "title": "Prepare concession boundaries",
                "rationale": "Defined boundaries prevent reactive movement.",
                "actions": ["Set limits before negotiating."],
                "example_language": ["That is the furthest I can move on price."],
                "success_indicator": "No unplanned concessions are made.",
            },
            {
                "priority": 1,
                "title": "Trade rather than concede",
                "rationale": "Conditional trades protect value.",
                "actions": ["Request reciprocal value."],
                "example_language": ["I can agree if payment terms improve."],
                "success_indicator": ("Every concession receives reciprocal value."),
            },
        ],
        "long_term_skills": ["Concession planning"],
        "preparation_checklist": ["Define reciprocal asks."],
        "avoid_next_time": ["Do not concede without receiving value."],
        "confidence": "high",
    }


def _build_extractor(
    response: str,
) -> tuple[StrategyExtractor, MagicMock, MagicMock]:
    prompt_builder = MagicMock(spec=StrategyPromptBuilder)
    prompt_builder.build_system_prompt.return_value = "strategy system prompt"
    prompt_builder.build_user_prompt.return_value = "strategy user prompt"
    provider = MagicMock(spec=LLMProvider)
    provider.generate.return_value = response
    return (
        StrategyExtractor(prompt_builder, provider),
        prompt_builder,
        provider,
    )


def test_valid_json_produces_strategy_and_sorts_unique_priorities() -> None:
    debrief_record = _create_debrief_record()
    extractor, prompt_builder, provider = _build_extractor(json.dumps(_valid_payload()))

    strategy = extractor.extract(debrief_record)

    assert strategy == _valid_strategy()
    assert [tactic.priority for tactic in strategy.prioritized_tactics] == [1, 2]
    prompt_builder.build_system_prompt.assert_called_once_with()
    prompt_builder.build_user_prompt.assert_called_once_with(debrief_record)
    provider.generate.assert_called_once_with(
        system_prompt="strategy system prompt",
        user_prompt="strategy user prompt",
    )


def test_fake_provider_returns_valid_strategy() -> None:
    extractor = StrategyExtractor(
        StrategyPromptBuilder(),
        FakeLLMProvider(),
    )

    strategy = extractor.extract(_create_debrief_record())

    assert strategy.primary_objective == (
        "Make concessions conditional on reciprocal value."
    )
    assert strategy.expected_outcome == (
        "Each concession advances the user toward a balanced agreement."
    )
    assert [tactic.priority for tactic in strategy.prioritized_tactics] == [1, 2]
    assert len(strategy.long_term_skills) < len(strategy.prioritized_tactics)


def test_extractor_rejects_empty_provider_response() -> None:
    extractor, _, _ = _build_extractor("   ")

    with pytest.raises(EmptyStrategyResponseError) as exc_info:
        extractor.extract(_create_debrief_record())

    assert str(exc_info.value) == (
        "The LLM provider returned an empty strategy response."
    )


def test_extractor_rejects_malformed_json_without_exposing_output() -> None:
    extractor, _, _ = _build_extractor("not JSON with private debrief data")

    with pytest.raises(InvalidStrategyJsonError) as exc_info:
        extractor.extract(_create_debrief_record())

    assert str(exc_info.value) == (
        "The LLM provider returned invalid JSON for strategy extraction."
    )
    assert "private debrief data" not in str(exc_info.value)


@pytest.mark.parametrize(
    "mutate_payload",
    [
        lambda payload: payload.pop("expected_outcome"),
        lambda payload: payload.update({"unexpected": "value"}),
        lambda payload: payload["prioritized_tactics"][0].update({"priority": "2"}),
        lambda payload: payload["prioritized_tactics"][0].update({"priority": 0}),
        lambda payload: payload["prioritized_tactics"][0].update({"priority": 1}),
        lambda payload: payload["prioritized_tactics"][0].update(
            {"unexpected": "value"}
        ),
    ],
    ids=[
        "missing-field",
        "extra-field",
        "non-strict-priority",
        "non-positive-priority",
        "duplicate-priority",
        "extra-tactic-field",
    ],
)
def test_extractor_rejects_invalid_strategy_data(
    mutate_payload: object,
) -> None:
    assert callable(mutate_payload)
    payload = _valid_payload()
    mutate_payload(payload)
    extractor, _, _ = _build_extractor(json.dumps(payload))

    with pytest.raises(InvalidStrategyDataError):
        extractor.extract(_create_debrief_record())


def test_provider_failure_propagates_unchanged() -> None:
    extractor, _, provider = _build_extractor(json.dumps(_valid_payload()))
    expected_error = RuntimeError("Provider failed")
    provider.generate.side_effect = expected_error

    with pytest.raises(RuntimeError) as exc_info:
        extractor.extract(_create_debrief_record())

    assert exc_info.value is expected_error


def test_extractor_has_no_repository_dependency() -> None:
    constructor_parameters = signature(StrategyExtractor.__init__).parameters
    extract_parameters = signature(StrategyExtractor.extract).parameters

    assert "repository" not in constructor_parameters
    assert list(extract_parameters) == ["self", "debrief_record"]


def test_service_generates_and_persists_strategy_from_debrief() -> None:
    session_id = uuid4()
    debrief_record = _create_debrief_record(session_id)
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    debrief_repository.get_by_session.return_value = debrief_record
    extractor = MagicMock(spec=StrategyExtractor)
    strategy = _valid_strategy()
    extractor.extract.return_value = strategy
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    strategy_repository.create.side_effect = lambda record: record
    service = StrategyService(
        debrief_repository,
        extractor,
        strategy_repository,
    )

    result = service.generate_for_session(session_id)

    assert isinstance(result, NegotiationStrategyRecord)
    assert isinstance(result.id, UUID)
    assert result.session_id == session_id
    assert result.debrief_id == debrief_record.id
    assert result.strategy is strategy
    assert result.created_at.tzinfo is not None
    assert result.created_at.utcoffset() == timedelta(0)
    debrief_repository.get_by_session.assert_called_once_with(session_id)
    extractor.extract.assert_called_once_with(debrief_record)
    strategy_repository.create.assert_called_once_with(result)


def test_service_prepares_strategy_from_supplied_debrief_without_persisting() -> None:
    session_id = uuid4()
    debrief_record = _create_debrief_record(session_id)
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    extractor = MagicMock(spec=StrategyExtractor)
    strategy = _valid_strategy()
    extractor.extract.return_value = strategy
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    service = StrategyService(debrief_repository, extractor, strategy_repository)

    result = service.prepare_for_session(session_id, debrief_record)

    assert result.session_id == session_id
    assert result.debrief_id == debrief_record.id
    assert result.strategy is strategy
    debrief_repository.get_by_session.assert_not_called()
    strategy_repository.create.assert_not_called()


def test_service_rejects_missing_debrief_before_extraction() -> None:
    session_id = uuid4()
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    debrief_repository.get_by_session.return_value = None
    extractor = MagicMock(spec=StrategyExtractor)
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    service = StrategyService(
        debrief_repository,
        extractor,
        strategy_repository,
    )

    with pytest.raises(NegotiationDebriefNotFoundError) as exc_info:
        service.generate_for_session(session_id)

    assert exc_info.value.session_id == session_id
    extractor.extract.assert_not_called()
    strategy_repository.create.assert_not_called()


def test_service_does_not_persist_when_extraction_fails() -> None:
    session_id = uuid4()
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    debrief_repository.get_by_session.return_value = _create_debrief_record(session_id)
    extractor = MagicMock(spec=StrategyExtractor)
    expected_error = InvalidStrategyDataError()
    extractor.extract.side_effect = expected_error
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    service = StrategyService(
        debrief_repository,
        extractor,
        strategy_repository,
    )

    with pytest.raises(InvalidStrategyDataError) as exc_info:
        service.generate_for_session(session_id)

    assert exc_info.value is expected_error
    strategy_repository.create.assert_not_called()


def test_duplicate_generation_extracts_then_repository_rejects() -> None:
    session_id = uuid4()
    debrief_repository = NegotiationDebriefRepository()
    debrief_repository.create(_create_debrief_record(session_id))
    extractor = MagicMock(spec=StrategyExtractor)
    extractor.extract.return_value = _valid_strategy()
    strategy_repository = NegotiationStrategyRepository()
    service = StrategyService(
        debrief_repository,
        extractor,
        strategy_repository,
    )
    original = service.generate_for_session(session_id)

    with pytest.raises(NegotiationStrategyAlreadyExistsError):
        service.generate_for_session(session_id)

    assert extractor.extract.call_count == 2
    assert strategy_repository.get_by_session(session_id) is original


def test_strategy_service_has_only_confirmed_dependencies() -> None:
    parameters = signature(StrategyService.__init__).parameters

    assert list(parameters) == [
        "self",
        "debrief_repository",
        "extractor",
        "strategy_repository",
    ]


def test_get_for_session_delegates_to_strategy_repository() -> None:
    session_id = uuid4()
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    extractor = MagicMock(spec=StrategyExtractor)
    strategy_repository = MagicMock(spec=NegotiationStrategyRepository)
    expected_record = NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=uuid4(),
        strategy=_valid_strategy(),
        created_at=datetime.now(UTC),
    )
    strategy_repository.get_by_session.return_value = expected_record
    service = StrategyService(
        debrief_repository,
        extractor,
        strategy_repository,
    )

    result = service.get_for_session(session_id)

    assert result is expected_record
    strategy_repository.get_by_session.assert_called_once_with(session_id)
