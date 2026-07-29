from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.prompts.opponent import OpponentPromptBuilder


def _create_scenario() -> Scenario:
    return Scenario(
        title="Enterprise software renewal",
        description="Negotiate the renewal of a multi-year software agreement.",
        industry="Technology",
        opponent_role="Vendor account executive",
        objective="Secure a three-year renewal at the current annual price.",
        difficulty=ScenarioDifficulty.ADVANCED,
        constraints=["Discount authority is limited to five percent."],
        personality="Confident and detail-oriented",
        negotiation_style="Competitive but pragmatic",
        hidden_context=["The vendor needs this deal to meet its quarterly target."],
        walk_away_conditions=["No agreement below the current annual contract value."],
    )


def _create_turn(
    *,
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


def test_system_prompt_includes_scenario_context() -> None:
    scenario = _create_scenario()

    prompt = OpponentPromptBuilder().build_system_prompt(scenario)

    assert scenario.opponent_role in prompt
    assert scenario.objective in prompt
    assert scenario.difficulty.value in prompt
    assert scenario.personality in prompt
    assert scenario.negotiation_style in prompt
    assert scenario.constraints[0] in prompt
    assert scenario.hidden_context[0] in prompt
    assert scenario.walk_away_conditions[0] in prompt


def test_system_prompt_protects_private_information() -> None:
    prompt = OpponentPromptBuilder().build_system_prompt(_create_scenario())

    assert "Never reveal or quote the private context" in prompt
    assert "walk-away conditions" in prompt
    assert "Do not reveal internal constraints directly" in prompt


def test_system_prompt_defines_opponent_behavior() -> None:
    prompt = OpponentPromptBuilder().build_system_prompt(_create_scenario())

    assert "Act only as the negotiation opponent" in prompt
    assert "remain in character" in prompt
    assert "Do not act as a coach or assistant" in prompt
    assert "Respond with only the opponent's message" in prompt
    assert 'Do not include labels such as "Opponent:"' in prompt


def test_system_prompt_is_deterministic() -> None:
    scenario = _create_scenario()
    builder = OpponentPromptBuilder()

    assert builder.build_system_prompt(scenario) == builder.build_system_prompt(
        scenario
    )


def test_user_prompt_renders_one_user_turn() -> None:
    session_id = uuid4()
    turn = _create_turn(
        session_id=session_id,
        turn_number=1,
        speaker=NegotiationTurnSpeaker.USER,
        content="We need a ten percent reduction.",
    )

    prompt = OpponentPromptBuilder().build_user_prompt([turn])

    assert "Turn 1 — User:\nWe need a ten percent reduction." in prompt


def test_user_prompt_renders_user_and_opponent_turns_in_order() -> None:
    session_id = uuid4()
    first = _create_turn(
        session_id=session_id,
        turn_number=1,
        speaker=NegotiationTurnSpeaker.USER,
        content="We need a ten percent reduction.",
    )
    second = _create_turn(
        session_id=session_id,
        turn_number=2,
        speaker=NegotiationTurnSpeaker.OPPONENT,
        content="We can consider a smaller adjustment.",
    )

    prompt = OpponentPromptBuilder().build_user_prompt([first, second])

    first_position = prompt.index("Turn 1 — User:")
    second_position = prompt.index("Turn 2 — Opponent:")
    assert first_position < second_position
    assert first.content in prompt
    assert second.content in prompt
    assert prompt.count(second.content) == 1


def test_user_prompt_ends_with_response_instruction() -> None:
    turn = _create_turn(
        session_id=uuid4(),
        turn_number=1,
        speaker=NegotiationTurnSpeaker.USER,
        content="Can you improve the offer?",
    )

    prompt = OpponentPromptBuilder().build_user_prompt([turn])

    assert prompt.endswith(
        "Respond to the latest user message as the negotiation opponent."
    )


def test_user_prompt_handles_empty_history() -> None:
    prompt = OpponentPromptBuilder().build_user_prompt([])

    assert "There is no prior negotiation history." in prompt
    assert "Begin the negotiation as the opponent" in prompt


def test_user_prompt_is_deterministic() -> None:
    turn = _create_turn(
        session_id=uuid4(),
        turn_number=1,
        speaker=NegotiationTurnSpeaker.USER,
        content="Can you improve the offer?",
    )
    builder = OpponentPromptBuilder()

    assert builder.build_user_prompt([turn]) == builder.build_user_prompt([turn])
