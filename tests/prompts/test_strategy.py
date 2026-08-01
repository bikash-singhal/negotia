from datetime import UTC, datetime
from inspect import signature
from uuid import uuid4

from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.prompts.strategy import StrategyPromptBuilder


def _create_debrief_record() -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=uuid4(),
        session_id=uuid4(),
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


def test_system_prompt_requires_actionable_prioritized_json_strategy() -> None:
    prompt = StrategyPromptBuilder().build_system_prompt()

    assert "expert negotiation strategy advisor" in prompt
    assert "actionable rather than merely descriptive" in prompt
    assert "positive, unique integers" in prompt
    assert "example language" in prompt
    assert "success indicator" in prompt
    assert "MUST return exactly one valid JSON object" in prompt
    assert "DO NOT wrap the JSON in Markdown or code fences" in prompt
    assert "do not include additional keys" in prompt
    assert prompt.rstrip().endswith("}")


def test_system_prompt_keeps_long_term_skills_fewer_than_tactics() -> None:
    prompt = StrategyPromptBuilder().build_system_prompt()

    assert (
        "Keep long-term skills more general and fewer than negotiation-specific tactics"
    ) in prompt


def test_user_prompt_contains_only_persisted_debrief_information() -> None:
    record = _create_debrief_record()

    prompt = StrategyPromptBuilder().build_user_prompt(record)

    assert str(record.id) in prompt
    assert str(record.session_id) in prompt
    assert "Observation count: 3" in prompt
    assert record.debrief.repeated_strengths[0] in prompt
    assert record.debrief.repeated_weaknesses[0] in prompt
    assert record.debrief.key_missed_opportunities[0] in prompt
    assert record.debrief.recurring_risks[0] in prompt
    assert record.debrief.overall_assessment in prompt
    assert record.debrief.confidence in prompt
    assert "conversation turn" not in prompt.lower()
    assert "scenario" not in prompt.lower()


def test_prompt_builder_accepts_only_debrief_record() -> None:
    parameters = signature(StrategyPromptBuilder.build_user_prompt).parameters

    assert list(parameters) == ["self", "record"]


def test_prompts_are_deterministic() -> None:
    builder = StrategyPromptBuilder()
    record = _create_debrief_record()

    assert builder.build_system_prompt() == builder.build_system_prompt()
    assert builder.build_user_prompt(record) == builder.build_user_prompt(record)
