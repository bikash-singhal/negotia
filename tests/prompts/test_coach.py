from datetime import UTC, datetime
from uuid import uuid4

from app.domains.adaptive_context.models import AdaptiveContext
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.prompts.coach import CoachPromptBuilder


def _create_turn(
    turn_number: int,
    speaker: NegotiationTurnSpeaker,
    content: str,
) -> NegotiationTurn:
    return NegotiationTurn(
        id=uuid4(),
        session_id=uuid4(),
        speaker=speaker,
        content=content,
        turn_number=turn_number,
        created_at=datetime.now(UTC),
    )


def test_system_prompt_defines_non_participating_coach_role() -> None:
    prompt = CoachPromptBuilder().build_system_prompt()

    assert "You are an expert negotiation coach" in prompt
    assert "You are NOT participating in the negotiation" in prompt
    assert "Evaluate only the user's negotiation behavior" in prompt
    assert "Base every observation on evidence from the conversation" in prompt


def test_system_prompt_forbids_invention_and_requires_json_only() -> None:
    prompt = CoachPromptBuilder().build_system_prompt()

    assert (
        "Do not invent strengths, weaknesses, missed opportunities, or risk signals"
        in prompt
    )
    assert "MUST return exactly one valid JSON object" in prompt
    assert "DO NOT wrap the JSON in Markdown or code fences" in prompt
    assert "do not include additional keys" in prompt
    assert prompt.rstrip().endswith("}")
    assert "explanations" in prompt


def test_system_prompt_omits_historical_section_without_context() -> None:
    prompt = CoachPromptBuilder().build_system_prompt(None)

    assert "Historical coaching context" not in prompt


def test_system_prompt_renders_coach_context_without_opponent_adjustments() -> None:
    context = AdaptiveContext(
        focus_areas=["Ask diagnostic questions"],
        coaching_focus=["Plan conditional concessions"],
        opponent_adjustments=["Increase resistance"],
        strengths=["Uses clear objective criteria"],
    )

    prompt = CoachPromptBuilder().build_system_prompt(context)

    assert "--- Historical coaching context ---" in prompt
    assert "Ask diagnostic questions" in prompt
    assert "Plan conditional concessions" in prompt
    assert "Uses clear objective criteria" in prompt
    assert "Increase resistance" not in prompt
    assert "Evaluate the current negotiation using current-session evidence" in prompt
    assert "Do not assume a historical weakness occurred again" in prompt
    assert (
        "Do not claim improvement or regression without supporting current-session "
        "evidence" in prompt
    )
    assert (
        "Use recurring strengths as observation context, not guaranteed current "
        "behavior" in prompt
    )


def test_user_prompt_contains_complete_ordered_speaker_labelled_history() -> None:
    first = _create_turn(
        1,
        NegotiationTurnSpeaker.USER,
        "We can commit for two years if the annual price decreases.",
    )
    second = _create_turn(
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "We can hold the price for a three-year commitment.",
    )

    prompt = CoachPromptBuilder().build_user_prompt([second, first])

    first_label = "Turn 1 - User:"
    second_label = "Turn 2 - Opponent:"
    assert prompt.index(first_label) < prompt.index(second_label)
    assert first.content in prompt
    assert second.content in prompt
    assert prompt.count(first.content) == 1
    assert prompt.count(second.content) == 1


def test_prompts_are_deterministic() -> None:
    turn = _create_turn(
        1,
        NegotiationTurnSpeaker.USER,
        "We need a ten percent reduction.",
    )
    builder = CoachPromptBuilder()
    context = AdaptiveContext(
        focus_areas=["Ask diagnostic questions"],
        coaching_focus=["Concession planning"],
        opponent_adjustments=[],
        strengths=["Uses conditional trades"],
    )

    assert builder.build_system_prompt() == builder.build_system_prompt()
    assert builder.build_system_prompt(context) == builder.build_system_prompt(context)
    assert builder.build_user_prompt([turn]) == builder.build_user_prompt([turn])
