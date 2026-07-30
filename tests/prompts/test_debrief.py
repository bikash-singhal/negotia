from datetime import UTC, datetime
from inspect import signature
from uuid import UUID, uuid4

from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.prompts.debrief import DebriefPromptBuilder


def _create_record(
    position: int,
    *,
    session_id: UUID,
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
            risk_signals=[f"Risk signal {position}"],
            confidence=f"confidence-{position}",
        ),
        created_at=datetime.now(UTC),
    )


def test_system_prompt_requires_supported_recurring_json_only_analysis() -> None:
    prompt = DebriefPromptBuilder().build_system_prompt()

    assert "expert negotiation debrief analyst" in prompt
    assert "Distinguish recurring behavior" in prompt
    assert "Rely only on the supplied coach observations" in prompt
    assert "Do not invent facts" in prompt
    assert "Do not re-evaluate dialogue" in prompt
    assert "Return only JSON" in prompt
    assert "no Markdown fences" in prompt


def test_user_prompt_preserves_order_and_includes_all_observation_fields() -> None:
    session_id = uuid4()
    first = _create_record(1, session_id=session_id)
    second = _create_record(2, session_id=session_id)

    prompt = DebriefPromptBuilder().build_user_prompt([first, second])

    assert prompt.index("Observation 1") < prompt.index("Observation 2")
    assert prompt.index(str(first.user_turn_id)) < prompt.index(
        str(second.user_turn_id)
    )
    for record in (first, second):
        assert str(record.user_turn_id) in prompt
        assert str(record.opponent_turn_id) in prompt
        assert record.observation.strengths[0] in prompt
        assert record.observation.weaknesses[0] in prompt
        assert record.observation.missed_opportunities[0] in prompt
        assert record.observation.risk_signals[0] in prompt
        assert record.observation.confidence in prompt


def test_prompt_builder_accepts_observations_without_raw_conversation() -> None:
    parameters = signature(DebriefPromptBuilder.build_user_prompt).parameters

    assert list(parameters) == ["self", "observations"]


def test_prompts_are_deterministic() -> None:
    records = [_create_record(1, session_id=uuid4())]
    builder = DebriefPromptBuilder()

    assert builder.build_system_prompt() == builder.build_system_prompt()
    assert builder.build_user_prompt(records) == builder.build_user_prompt(records)
