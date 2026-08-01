import json
import logging
from unittest.mock import MagicMock

import pytest

from app.domains.negotiation_state.exceptions import (
    EmptyNegotiationStateResponseError,
    InvalidNegotiationStateDataError,
    InvalidNegotiationStateJsonError,
)
from app.domains.negotiation_state.models import NegotiationState
from app.llm.provider import LLMProvider
from app.prompts.negotiation_state import NegotiationStatePromptBuilder
from app.services.negotiation_state import NegotiationStateExtractor


def _build_extractor(
    response: str,
) -> tuple[
    NegotiationStateExtractor,
    MagicMock,
    MagicMock,
]:
    prompt_builder = MagicMock(spec=NegotiationStatePromptBuilder)
    prompt_builder.build_system_prompt.return_value = "state system prompt"
    prompt_builder.build_user_prompt.return_value = "state user prompt"
    provider = MagicMock(spec=LLMProvider)
    provider.generate.return_value = response
    return (
        NegotiationStateExtractor(prompt_builder, provider),
        prompt_builder,
        provider,
    )


def test_valid_json_produces_negotiation_state() -> None:
    response = json.dumps(
        {
            "latest_user_position": "A two-year term with a ten percent discount.",
            "latest_opponent_position": "Current pricing for a two-year term.",
            "agreements": ["Both sides prefer a multi-year agreement."],
            "open_topics": ["Annual price", "Contract length"],
            "unresolved_items": ["Discount percentage"],
            "negotiation_stage": "bargaining",
        }
    )
    extractor, prompt_builder, provider = _build_extractor(response)

    state = extractor.extract([])

    assert state == NegotiationState(
        latest_user_position="A two-year term with a ten percent discount.",
        latest_opponent_position="Current pricing for a two-year term.",
        agreements=["Both sides prefer a multi-year agreement."],
        open_topics=["Annual price", "Contract length"],
        unresolved_items=["Discount percentage"],
        negotiation_stage="bargaining",
    )
    prompt_builder.build_system_prompt.assert_called_once_with()
    prompt_builder.build_user_prompt.assert_called_once_with([])
    provider.generate.assert_called_once_with(
        system_prompt="state system prompt",
        user_prompt="state user prompt",
        temperature=0.0,
    )


def test_json_with_surrounding_whitespace_is_accepted() -> None:
    response = (
        "  \n"
        + json.dumps(
            {
                "latest_user_position": None,
                "latest_opponent_position": None,
                "agreements": [],
                "open_topics": [],
                "unresolved_items": [],
                "negotiation_stage": "opening",
            }
        )
        + "\n  "
    )
    extractor, _, _ = _build_extractor(response)

    state = extractor.extract([])

    assert state.negotiation_stage == "opening"


@pytest.mark.parametrize("opening_fence", ["```json", "```"])
def test_one_outer_markdown_fence_is_removed(opening_fence: str) -> None:
    payload = json.dumps(
        {
            "latest_user_position": None,
            "latest_opponent_position": None,
            "agreements": [],
            "open_topics": [],
            "unresolved_items": [],
            "negotiation_stage": "opening",
        }
    )
    extractor, _, _ = _build_extractor(f"  {opening_fence}\n{payload}\n```  ")

    state = extractor.extract([])

    assert state.negotiation_stage == "opening"


def test_explanatory_preamble_is_rejected() -> None:
    response = (
        "Here is the requested state:\n"
        '{"latest_user_position": null, "latest_opponent_position": null, '
        '"agreements": [], "open_topics": [], "unresolved_items": [], '
        '"negotiation_stage": "opening"}'
    )
    extractor, _, _ = _build_extractor(response)

    with pytest.raises(InvalidNegotiationStateJsonError):
        extractor.extract([])


def test_empty_lists_and_null_positions_are_supported() -> None:
    response = json.dumps(
        {
            "latest_user_position": None,
            "latest_opponent_position": None,
            "agreements": [],
            "open_topics": [],
            "unresolved_items": [],
            "negotiation_stage": "opening",
        }
    )
    extractor, _, _ = _build_extractor(response)

    state = extractor.extract([])

    assert state.latest_user_position is None
    assert state.latest_opponent_position is None
    assert state.agreements == []
    assert state.open_topics == []
    assert state.unresolved_items == []
    assert state.negotiation_stage == "opening"


def test_empty_response_raises_expected_exception() -> None:
    extractor, _, _ = _build_extractor("   ")

    with pytest.raises(EmptyNegotiationStateResponseError) as exc_info:
        extractor.extract([])

    assert str(exc_info.value) == (
        "The LLM provider returned an empty negotiation state response."
    )


def test_invalid_json_raises_expected_exception_without_raw_output() -> None:
    extractor, _, _ = _build_extractor("not valid JSON with private content")

    with pytest.raises(InvalidNegotiationStateJsonError) as exc_info:
        extractor.extract([])

    assert str(exc_info.value) == (
        "The LLM provider returned invalid JSON for negotiation state extraction."
    )
    assert "private content" not in str(exc_info.value)


def test_invalid_output_logs_only_safe_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_output = "sensitive raw negotiation output"
    extractor, _, _ = _build_extractor(sensitive_output)
    state_logger = logging.getLogger("app.services.negotiation_state")
    previous_disabled = state_logger.disabled
    state_logger.disabled = False
    caplog.set_level(logging.WARNING, logger="app.services.negotiation_state")

    try:
        with pytest.raises(InvalidNegotiationStateJsonError):
            extractor.extract([])
    finally:
        state_logger.disabled = previous_disabled

    parse_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "negotiation_state_parse_failed"
    )
    assert getattr(parse_record, "output_length", None) == len(sensitive_output)
    assert getattr(parse_record, "fence_detected", None) is False
    assert getattr(parse_record, "failure_category", None) == "invalid_json"
    assert sensitive_output not in "\n".join(
        record.getMessage() for record in caplog.records
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "latest_user_position": None,
            "latest_opponent_position": None,
            "agreements": [],
            "open_topics": [],
            "unresolved_items": [],
        },
        {
            "latest_user_position": None,
            "latest_opponent_position": None,
            "agreements": "none",
            "open_topics": [],
            "unresolved_items": [],
            "negotiation_stage": "opening",
        },
        {
            "latest_user_position": None,
            "latest_opponent_position": None,
            "agreements": [],
            "open_topics": [],
            "unresolved_items": [],
            "negotiation_stage": "opening",
            "unexpected": "value",
        },
    ],
    ids=["missing-field", "invalid-field-type", "unexpected-field"],
)
def test_structurally_invalid_data_raises_expected_exception(
    payload: dict[str, object],
) -> None:
    extractor, _, _ = _build_extractor(json.dumps(payload))

    with pytest.raises(InvalidNegotiationStateDataError) as exc_info:
        extractor.extract([])

    assert str(exc_info.value) == (
        "The LLM provider returned structurally invalid negotiation state data."
    )
