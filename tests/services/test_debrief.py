import json
from datetime import UTC, datetime, timedelta
from inspect import signature
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.coach.repository import CoachObservationRepository
from app.domains.debrief.exceptions import (
    EmptyDebriefResponseError,
    InvalidDebriefDataError,
    InvalidDebriefJsonError,
    NegotiationDebriefAlreadyExistsError,
    NoCoachObservationsError,
)
from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider
from app.prompts.debrief import DebriefPromptBuilder
from app.services.debrief import DebriefExtractor, DebriefService


def _create_observation_record(
    session_id: UUID,
    position: int = 1,
) -> CoachObservationRecord:
    return CoachObservationRecord(
        id=uuid4(),
        session_id=session_id,
        user_turn_id=uuid4(),
        opponent_turn_id=uuid4(),
        observation=CoachObservation(
            strengths=[f"Strength {position}"],
            weaknesses=[f"Weakness {position}"],
            missed_opportunities=[f"Missed opportunity {position}"],
            risk_signals=[f"Risk {position}"],
            confidence="high",
        ),
        created_at=datetime.now(UTC),
    )


def _valid_debrief() -> NegotiationDebrief:
    return NegotiationDebrief(
        repeated_strengths=["Uses conditional trades."],
        repeated_weaknesses=["Anchors too early."],
        key_missed_opportunities=["Did not test the deadline."],
        recurring_risks=["Concedes without receiving value."],
        overall_assessment="Constructive, but too quick to concede.",
        confidence="high",
    )


def _valid_response() -> str:
    return json.dumps(
        {
            "repeated_strengths": ["Uses conditional trades."],
            "repeated_weaknesses": ["Anchors too early."],
            "key_missed_opportunities": ["Did not test the deadline."],
            "recurring_risks": ["Concedes without receiving value."],
            "overall_assessment": "Constructive, but too quick to concede.",
            "confidence": "high",
        }
    )


def _build_extractor(
    response: str,
) -> tuple[DebriefExtractor, MagicMock, MagicMock]:
    prompt_builder = MagicMock(spec=DebriefPromptBuilder)
    prompt_builder.build_system_prompt.return_value = "debrief system prompt"
    prompt_builder.build_user_prompt.return_value = "debrief user prompt"
    provider = MagicMock(spec=LLMProvider)
    provider.generate.return_value = response
    return (
        DebriefExtractor(prompt_builder, provider),
        prompt_builder,
        provider,
    )


def test_valid_json_produces_debrief_and_passes_exact_prompts() -> None:
    record = _create_observation_record(uuid4())
    extractor, prompt_builder, provider = _build_extractor(_valid_response())

    debrief = extractor.extract([record])

    assert debrief == _valid_debrief()
    prompt_builder.build_system_prompt.assert_called_once_with()
    prompt_builder.build_user_prompt.assert_called_once_with([record])
    provider.generate.assert_called_once_with(
        system_prompt="debrief system prompt",
        user_prompt="debrief user prompt",
    )


def test_fake_provider_returns_valid_debrief() -> None:
    extractor = DebriefExtractor(
        DebriefPromptBuilder(),
        FakeLLMProvider(),
    )

    debrief = extractor.extract([_create_observation_record(uuid4())])

    assert debrief == NegotiationDebrief(
        repeated_strengths=[],
        repeated_weaknesses=[],
        key_missed_opportunities=[],
        recurring_risks=[],
        overall_assessment=("There is not enough evidence for a detailed assessment."),
        confidence="low",
    )


def test_extractor_rejects_empty_observations_before_prompt_or_provider() -> None:
    extractor, prompt_builder, provider = _build_extractor(_valid_response())

    with pytest.raises(NoCoachObservationsError):
        extractor.extract([])

    prompt_builder.build_system_prompt.assert_not_called()
    prompt_builder.build_user_prompt.assert_not_called()
    provider.generate.assert_not_called()


def test_extractor_rejects_empty_provider_response() -> None:
    extractor, _, _ = _build_extractor("   ")

    with pytest.raises(EmptyDebriefResponseError) as exc_info:
        extractor.extract([_create_observation_record(uuid4())])

    assert str(exc_info.value) == (
        "The LLM provider returned an empty debrief response."
    )


def test_extractor_rejects_malformed_json_without_exposing_output() -> None:
    extractor, _, _ = _build_extractor("not JSON with private observations")

    with pytest.raises(InvalidDebriefJsonError) as exc_info:
        extractor.extract([_create_observation_record(uuid4())])

    assert str(exc_info.value) == (
        "The LLM provider returned invalid JSON for debrief extraction."
    )
    assert "private observations" not in str(exc_info.value)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "repeated_strengths": [],
            "repeated_weaknesses": [],
            "key_missed_opportunities": [],
            "recurring_risks": [],
            "overall_assessment": "Evidence is limited.",
        },
        {
            "repeated_strengths": [],
            "repeated_weaknesses": [],
            "key_missed_opportunities": [],
            "recurring_risks": [],
            "overall_assessment": "Evidence is limited.",
            "confidence": "low",
            "unexpected": "value",
        },
    ],
    ids=["missing-field", "extra-field"],
)
def test_extractor_rejects_structurally_invalid_data(
    payload: dict[str, object],
) -> None:
    extractor, _, _ = _build_extractor(json.dumps(payload))

    with pytest.raises(InvalidDebriefDataError):
        extractor.extract([_create_observation_record(uuid4())])


def test_extractor_has_no_repository_dependency() -> None:
    constructor_parameters = signature(DebriefExtractor.__init__).parameters
    extract_parameters = signature(DebriefExtractor.extract).parameters

    assert "repository" not in constructor_parameters
    assert list(extract_parameters) == ["self", "observations"]


def test_service_loads_all_observations_in_order_and_persists_record() -> None:
    session_id = uuid4()
    first = _create_observation_record(session_id, 1)
    second = _create_observation_record(session_id, 2)
    coach_repository = MagicMock(spec=CoachObservationRepository)
    coach_repository.list_by_session.return_value = [first, second]
    extractor = MagicMock(spec=DebriefExtractor)
    debrief = _valid_debrief()
    extractor.extract.return_value = debrief
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    debrief_repository.create.side_effect = lambda record: record
    service = DebriefService(
        coach_repository,
        extractor,
        debrief_repository,
    )

    result = service.generate_for_session(session_id)

    assert isinstance(result, NegotiationDebriefRecord)
    assert isinstance(result.id, UUID)
    assert result.session_id == session_id
    assert result.debrief is debrief
    assert result.observation_count == 2
    assert result.created_at.tzinfo is not None
    assert result.created_at.utcoffset() == timedelta(0)
    coach_repository.list_by_session.assert_called_once_with(session_id)
    extractor.extract.assert_called_once_with([first, second])
    debrief_repository.create.assert_called_once_with(result)


def test_service_prepares_debrief_without_persisting() -> None:
    session_id = uuid4()
    observations = [_create_observation_record(session_id, 1)]
    coach_repository = MagicMock(spec=CoachObservationRepository)
    coach_repository.list_by_session.return_value = observations
    extractor = MagicMock(spec=DebriefExtractor)
    debrief = _valid_debrief()
    extractor.extract.return_value = debrief
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    service = DebriefService(coach_repository, extractor, debrief_repository)

    result = service.prepare_for_session(session_id)

    assert result.session_id == session_id
    assert result.debrief is debrief
    debrief_repository.create.assert_not_called()


def test_service_rejects_session_without_observations() -> None:
    coach_repository = MagicMock(spec=CoachObservationRepository)
    coach_repository.list_by_session.return_value = []
    extractor = MagicMock(spec=DebriefExtractor)
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    service = DebriefService(
        coach_repository,
        extractor,
        debrief_repository,
    )

    with pytest.raises(NoCoachObservationsError):
        service.generate_for_session(uuid4())

    extractor.extract.assert_not_called()
    debrief_repository.create.assert_not_called()


def test_service_does_not_persist_when_extraction_fails() -> None:
    session_id = uuid4()
    coach_repository = MagicMock(spec=CoachObservationRepository)
    coach_repository.list_by_session.return_value = [
        _create_observation_record(session_id)
    ]
    extractor = MagicMock(spec=DebriefExtractor)
    expected_error = InvalidDebriefDataError()
    extractor.extract.side_effect = expected_error
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    service = DebriefService(
        coach_repository,
        extractor,
        debrief_repository,
    )

    with pytest.raises(InvalidDebriefDataError) as exc_info:
        service.generate_for_session(session_id)

    assert exc_info.value is expected_error
    debrief_repository.create.assert_not_called()


def test_duplicate_generation_is_rejected_without_overwriting_original() -> None:
    session_id = uuid4()
    coach_repository = CoachObservationRepository()
    coach_repository.create(_create_observation_record(session_id))
    extractor = MagicMock(spec=DebriefExtractor)
    extractor.extract.return_value = _valid_debrief()
    debrief_repository = NegotiationDebriefRepository()
    service = DebriefService(
        coach_repository,
        extractor,
        debrief_repository,
    )
    original = service.generate_for_session(session_id)

    with pytest.raises(NegotiationDebriefAlreadyExistsError):
        service.generate_for_session(session_id)

    assert debrief_repository.get_by_session(session_id) is original


def test_service_has_no_turn_or_scenario_repository_dependency() -> None:
    parameters = signature(DebriefService.__init__).parameters

    assert "turn_repository" not in parameters
    assert "scenario_repository" not in parameters


def test_get_for_session_delegates_to_debrief_repository() -> None:
    session_id = uuid4()
    coach_repository = MagicMock(spec=CoachObservationRepository)
    extractor = MagicMock(spec=DebriefExtractor)
    debrief_repository = MagicMock(spec=NegotiationDebriefRepository)
    expected_record = NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=_valid_debrief(),
        observation_count=1,
        created_at=datetime.now(UTC),
    )
    debrief_repository.get_by_session.return_value = expected_record
    service = DebriefService(
        coach_repository,
        extractor,
        debrief_repository,
    )

    result = service.get_for_session(session_id)

    assert result is expected_record
    debrief_repository.get_by_session.assert_called_once_with(session_id)
