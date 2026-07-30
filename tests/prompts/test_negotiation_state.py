from datetime import UTC, datetime
from uuid import uuid4

from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.prompts.negotiation_state import NegotiationStatePromptBuilder


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


def test_system_prompt_defines_state_extraction_task_and_json_structure() -> None:
    prompt = NegotiationStatePromptBuilder().build_system_prompt()

    assert "not responding as the negotiation opponent" in prompt
    assert '"latest_user_position"' in prompt
    assert '"latest_opponent_position"' in prompt
    assert '"agreements"' in prompt
    assert '"open_topics"' in prompt
    assert '"unresolved_items"' in prompt
    assert '"negotiation_stage"' in prompt
    assert "Return only JSON" in prompt
    assert "no Markdown fences" in prompt


def test_system_prompt_forbids_invention() -> None:
    prompt = NegotiationStatePromptBuilder().build_system_prompt()

    assert "Do not invent agreements, offers, open topics, or unresolved issues" in (
        prompt
    )
    assert "concise, factual descriptions" in prompt
    assert "Distinguish the user's position from the opponent's position" in prompt


def test_user_prompt_contains_complete_ordered_speaker_labelled_history() -> None:
    first = _create_turn(
        1,
        NegotiationTurnSpeaker.USER,
        "We can commit for two years at a lower annual price.",
    )
    second = _create_turn(
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "A two-year term requires the current annual price.",
    )

    prompt = NegotiationStatePromptBuilder().build_user_prompt([second, first])

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
    builder = NegotiationStatePromptBuilder()

    assert builder.build_system_prompt() == builder.build_system_prompt()
    assert builder.build_user_prompt([turn]) == builder.build_user_prompt([turn])
