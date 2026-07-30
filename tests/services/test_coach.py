import json
from unittest.mock import MagicMock

import pytest

from app.domains.coach.exceptions import (
    EmptyCoachObservationResponseError,
    InvalidCoachObservationDataError,
    InvalidCoachObservationJsonError,
)
from app.domains.coach.models import CoachObservation
from app.domains.negotiation_turn.models import NegotiationTurn
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider
from app.prompts.coach import CoachPromptBuilder
from app.services.coach import CoachObservationExtractor, CoachService


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

    observation = extractor.extract([])

    assert observation == CoachObservation(
        strengths=["Connected contract length to price."],
        weaknesses=["Did not explain the business value of the proposal."],
        missed_opportunities=["Could have asked about renewal timing."],
        risk_signals=["Anchored before learning the opponent's priorities."],
        confidence="high",
    )
    prompt_builder.build_system_prompt.assert_called_once_with()
    prompt_builder.build_user_prompt.assert_called_once_with([])
    provider.generate.assert_called_once_with(
        system_prompt="coach system prompt",
        user_prompt="coach user prompt",
    )


def test_fake_provider_returns_valid_coach_observation() -> None:
    extractor = CoachObservationExtractor(
        CoachPromptBuilder(),
        FakeLLMProvider(),
    )

    observation = extractor.extract([])

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
        extractor.extract([])

    assert str(exc_info.value) == (
        "The LLM provider returned an empty coach observation response."
    )


def test_invalid_json_raises_expected_exception_without_raw_output() -> None:
    extractor, _, _ = _build_extractor("not JSON with private conversation data")

    with pytest.raises(InvalidCoachObservationJsonError) as exc_info:
        extractor.extract([])

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
        extractor.extract([])

    assert str(exc_info.value) == (
        "The LLM provider returned structurally invalid coach observation data."
    )


def test_coach_service_delegates_without_persistence() -> None:
    observation = CoachObservation(
        strengths=["Used a conditional trade."],
        weaknesses=[],
        missed_opportunities=[],
        risk_signals=[],
        confidence="medium",
    )
    extractor = MagicMock(spec=CoachObservationExtractor)
    extractor.extract.return_value = observation
    service = CoachService(extractor)
    turns: list[NegotiationTurn] = []

    result = service.analyze(turns)

    assert result is observation
    extractor.extract.assert_called_once_with(turns)
    assert not any("repository" in name for name in vars(service))
