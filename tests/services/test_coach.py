import json
from datetime import UTC, datetime, timedelta
from inspect import signature
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.adaptive_context.models import AdaptiveContext
from app.domains.coach.exceptions import (
    EmptyCoachObservationResponseError,
    InvalidCoachExchangeError,
    InvalidCoachObservationDataError,
    InvalidCoachObservationJsonError,
)
from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.coach.repository import CoachObservationRepository
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider
from app.prompts.coach import CoachPromptBuilder
from app.services.adaptive_context import AdaptiveContextService
from app.services.coach import CoachObservationExtractor, CoachService
from tests.ownership import TEST_USER_ID


def _build_extractor(
    response: str,
) -> tuple[
    CoachObservationExtractor,
    MagicMock,
    MagicMock,
]:
    prompt_builder = MagicMock(spec=CoachPromptBuilder)
    prompt_builder.build_system_prompt.return_value = "coach system prompt"
    prompt_builder.build_user_prompt.return_value = "coach user prompt"
    provider = MagicMock(spec=LLMProvider)
    provider.generate.return_value = response
    return (
        CoachObservationExtractor(prompt_builder, provider),
        prompt_builder,
        provider,
    )


def test_valid_json_produces_coach_observation() -> None:
    response = json.dumps(
        {
            "strengths": ["Connected contract length to price."],
            "weaknesses": ["Did not explain the business value of the proposal."],
            "missed_opportunities": ["Could have asked about renewal timing."],
            "risk_signals": ["Anchored before learning the opponent's priorities."],
            "confidence": "high",
        }
    )
    extractor, prompt_builder, provider = _build_extractor(response)

    observation = extractor.extract([], None)

    assert observation == CoachObservation(
        strengths=["Connected contract length to price."],
        weaknesses=["Did not explain the business value of the proposal."],
        missed_opportunities=["Could have asked about renewal timing."],
        risk_signals=["Anchored before learning the opponent's priorities."],
        confidence="high",
    )
    prompt_builder.build_system_prompt.assert_called_once_with(None)
    prompt_builder.build_user_prompt.assert_called_once_with([])
    provider.generate.assert_called_once_with(
        system_prompt="coach system prompt",
        user_prompt="coach user prompt",
        temperature=0.0,
    )


def test_fake_provider_returns_valid_coach_observation() -> None:
    extractor = CoachObservationExtractor(
        CoachPromptBuilder(),
        FakeLLMProvider(),
    )

    observation = extractor.extract([], None)

    assert observation == CoachObservation(
        strengths=[],
        weaknesses=[],
        missed_opportunities=[],
        risk_signals=[],
        confidence="low",
    )


def test_empty_response_raises_expected_exception() -> None:
    extractor, _, _ = _build_extractor("   ")

    with pytest.raises(EmptyCoachObservationResponseError) as exc_info:
        extractor.extract([], None)

    assert str(exc_info.value) == (
        "The LLM provider returned an empty coach observation response."
    )


def test_invalid_json_raises_expected_exception_without_raw_output() -> None:
    extractor, _, _ = _build_extractor("not JSON with private conversation data")

    with pytest.raises(InvalidCoachObservationJsonError) as exc_info:
        extractor.extract([], None)

    assert str(exc_info.value) == (
        "The LLM provider returned invalid JSON for coach observation extraction."
    )
    assert "private conversation data" not in str(exc_info.value)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "strengths": [],
            "weaknesses": [],
            "missed_opportunities": [],
            "risk_signals": [],
        },
        {
            "strengths": "none",
            "weaknesses": [],
            "missed_opportunities": [],
            "risk_signals": [],
            "confidence": "low",
        },
        {
            "strengths": [],
            "weaknesses": [],
            "missed_opportunities": [],
            "risk_signals": [],
            "confidence": "low",
            "unexpected": "value",
        },
    ],
    ids=["missing-field", "invalid-field-type", "unexpected-field"],
)
def test_invalid_schema_raises_expected_exception(
    payload: dict[str, object],
) -> None:
    extractor, _, _ = _build_extractor(json.dumps(payload))

    with pytest.raises(InvalidCoachObservationDataError) as exc_info:
        extractor.extract([], None)

    assert str(exc_info.value) == (
        "The LLM provider returned structurally invalid coach observation data."
    )


def _create_turn(
    session_id: UUID,
    turn_number: int,
    speaker: NegotiationTurnSpeaker,
    content: str,
) -> NegotiationTurn:
    return NegotiationTurn(
        id=uuid4(),
        session_id=session_id,
        speaker=speaker,
        content=content,
        turn_number=turn_number,
        created_at=datetime.now(UTC),
    )


def test_coach_service_extracts_and_persists_latest_exchange() -> None:
    session_id = uuid4()
    prior_user_turn = _create_turn(
        session_id,
        1,
        NegotiationTurnSpeaker.USER,
        "We can consider a two-year term.",
    )
    prior_opponent_turn = _create_turn(
        session_id,
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "We require a three-year term.",
    )
    latest_user_turn = _create_turn(
        session_id,
        3,
        NegotiationTurnSpeaker.USER,
        "Could a larger upfront payment support two years?",
    )
    opponent_turn = _create_turn(
        session_id,
        4,
        NegotiationTurnSpeaker.OPPONENT,
        "A larger upfront payment could support that term.",
    )
    turns = [
        prior_user_turn,
        prior_opponent_turn,
        latest_user_turn,
        opponent_turn,
    ]
    observation = CoachObservation(
        strengths=["Used a conditional trade."],
        weaknesses=[],
        missed_opportunities=[],
        risk_signals=[],
        confidence="medium",
    )
    extractor = MagicMock(spec=CoachObservationExtractor)
    extractor.extract.return_value = observation
    repository = MagicMock(spec=CoachObservationRepository)
    repository.create.side_effect = lambda record, user_id: record
    adaptive_context = AdaptiveContext(
        focus_areas=["Diagnostic questioning"],
        coaching_focus=["Concession planning"],
        opponent_adjustments=["Apply more pressure"],
        strengths=["Conditional concessions"],
    )
    adaptive_context_service = MagicMock(spec=AdaptiveContextService)
    adaptive_context_service.get_context.return_value = adaptive_context
    service = CoachService(extractor, repository, adaptive_context_service)

    result = service.analyze_exchange(
        session_id,
        TEST_USER_ID,
        turns,
        latest_user_turn,
        opponent_turn,
    )

    assert isinstance(result, CoachObservationRecord)
    assert isinstance(result.id, UUID)
    assert result.session_id == session_id
    assert result.user_turn_id == latest_user_turn.id
    assert result.opponent_turn_id == opponent_turn.id
    assert result.observation is observation
    assert result.created_at.tzinfo is not None
    assert result.created_at.utcoffset() == timedelta(0)
    adaptive_context_service.get_context.assert_called_once_with(TEST_USER_ID)
    extractor.extract.assert_called_once_with(turns, adaptive_context)
    repository.create.assert_called_once_with(result, TEST_USER_ID)


def test_coach_service_preserves_standard_behavior_without_context() -> None:
    session_id = uuid4()
    user_turn = _create_turn(
        session_id,
        1,
        NegotiationTurnSpeaker.USER,
        "We can commit for two years.",
    )
    opponent_turn = _create_turn(
        session_id,
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "We require a three-year term.",
    )
    turns = [user_turn, opponent_turn]
    observation = CoachObservation(
        strengths=[],
        weaknesses=[],
        missed_opportunities=[],
        risk_signals=[],
        confidence="low",
    )
    extractor = MagicMock(spec=CoachObservationExtractor)
    extractor.extract.return_value = observation
    repository = MagicMock(spec=CoachObservationRepository)
    repository.create.side_effect = lambda record, user_id: record
    adaptive_context_service = MagicMock(spec=AdaptiveContextService)
    adaptive_context_service.get_context.return_value = None
    service = CoachService(extractor, repository, adaptive_context_service)

    result = service.analyze_exchange(
        session_id,
        TEST_USER_ID,
        turns,
        user_turn,
        opponent_turn,
    )

    adaptive_context_service.get_context.assert_called_once_with(TEST_USER_ID)
    extractor.extract.assert_called_once_with(turns, None)
    repository.create.assert_called_once_with(result, TEST_USER_ID)


def test_coach_service_rejects_non_latest_user_turn() -> None:
    session_id = uuid4()
    earlier_user_turn = _create_turn(
        session_id,
        1,
        NegotiationTurnSpeaker.USER,
        "We need a shorter term.",
    )
    latest_user_turn = _create_turn(
        session_id,
        2,
        NegotiationTurnSpeaker.USER,
        "We can increase the upfront payment.",
    )
    opponent_turn = _create_turn(
        session_id,
        3,
        NegotiationTurnSpeaker.OPPONENT,
        "That could support a shorter term.",
    )
    turns = [earlier_user_turn, latest_user_turn, opponent_turn]
    extractor = MagicMock(spec=CoachObservationExtractor)
    repository = MagicMock(spec=CoachObservationRepository)
    adaptive_context_service = MagicMock(spec=AdaptiveContextService)
    service = CoachService(extractor, repository, adaptive_context_service)

    with pytest.raises(InvalidCoachExchangeError):
        service.analyze_exchange(
            session_id,
            TEST_USER_ID,
            turns,
            earlier_user_turn,
            opponent_turn,
        )

    adaptive_context_service.get_context.assert_not_called()
    extractor.extract.assert_not_called()
    repository.create.assert_not_called()


def test_coach_service_has_no_turn_repository_dependency() -> None:
    parameters = signature(CoachService.__init__).parameters

    assert "turn_repository" not in parameters
    assert "adaptive_context_service" in parameters
    assert "memory_service" not in parameters
    assert "memory_repository" not in parameters
