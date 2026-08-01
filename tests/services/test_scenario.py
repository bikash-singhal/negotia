import logging
from unittest.mock import MagicMock

import pytest

from app.domains.scenario.exceptions import (
    EmptyScenarioGenerationResponseError,
    InvalidScenarioGenerationDataError,
    InvalidScenarioGenerationJsonError,
)
from app.domains.scenario.models import ScenarioDifficulty
from app.domains.scenario.schemas import ScenarioGenerateRequest
from app.llm.provider import LLMProvider
from app.prompts.scenario import ScenarioPromptBuilder
from app.services.scenario import ScenarioGenerator

VALID_RESPONSE = (
    '{"industry": "Technology", "opponent_role": "Recruiter", '
    '"objective": "Improve total compensation.", '
    '"personality": "Professional and pragmatic", '
    '"negotiation_style": "Collaborative", '
    '"constraints": ["Approved compensation band"], '
    '"hidden_context": ["Equity is flexible"], '
    '"walk_away_conditions": ["Candidate rejects all package components"]}'
)


def _request() -> ScenarioGenerateRequest:
    return ScenarioGenerateRequest(
        title="Salary negotiation at Microsoft",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        description="Negotiate an improved compensation package professionally.",
    )


def _generator(response: str) -> tuple[ScenarioGenerator, MagicMock]:
    provider = MagicMock(spec=LLMProvider)
    provider.generate.return_value = response
    return ScenarioGenerator(ScenarioPromptBuilder(), provider), provider


@pytest.mark.parametrize(
    "response",
    [VALID_RESPONSE, f"  \n{VALID_RESPONSE}\n  ", f"```json\n{VALID_RESPONSE}\n```"],
)
def test_generate_accepts_supported_structured_json(response: str) -> None:
    generator, provider = _generator(response)

    generated = generator.generate(_request())

    assert generated.industry == "Technology"
    assert generated.opponent_role == "Recruiter"
    assert generated.hidden_context == ["Equity is flexible"]
    provider.generate.assert_called_once()
    assert provider.generate.call_args.kwargs["temperature"] == 0.0


def test_generate_rejects_blank_response() -> None:
    generator, _ = _generator("  \n")

    with pytest.raises(EmptyScenarioGenerationResponseError):
        generator.generate(_request())


def test_generate_rejects_malformed_json() -> None:
    generator, _ = _generator("not-json")

    with pytest.raises(InvalidScenarioGenerationJsonError):
        generator.generate(_request())


@pytest.mark.parametrize(
    "response",
    [
        "{}",
        VALID_RESPONSE.removesuffix("}") + ', "unexpected": true}',
        VALID_RESPONSE.replace(
            '["Approved compensation band"]',
            '"Approved compensation band"',
        ),
    ],
)
def test_generate_rejects_invalid_schema(response: str) -> None:
    generator, _ = _generator(response)

    with pytest.raises(InvalidScenarioGenerationDataError):
        generator.generate(_request())


def test_generate_does_not_log_raw_output(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_output = "sensitive-scenario-output"
    generator, _ = _generator(sensitive_output)

    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(InvalidScenarioGenerationJsonError),
    ):
        generator.generate(_request())

    assert sensitive_output not in caplog.text
