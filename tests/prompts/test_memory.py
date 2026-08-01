from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
    NegotiationTactic,
)
from app.prompts.memory import MemoryPromptBuilder


def _create_records(
    session_id: UUID,
    marker: str,
) -> tuple[NegotiationDebriefRecord, NegotiationStrategyRecord]:
    debrief = NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=NegotiationDebrief(
            repeated_strengths=[f"{marker} conditional concessions"],
            repeated_weaknesses=[f"{marker} early anchoring"],
            key_missed_opportunities=[f"{marker} deadline discovery"],
            recurring_risks=[f"{marker} unilateral concessions"],
            overall_assessment=f"{marker} persisted assessment",
            confidence="high",
        ),
        observation_count=2,
        created_at=datetime.now(UTC),
    )
    strategy = NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=debrief.id,
        strategy=NegotiationStrategy(
            primary_objective=f"{marker} conditional trades",
            expected_outcome=f"{marker} reciprocal value",
            prioritized_tactics=[
                NegotiationTactic(
                    priority=1,
                    title=f"{marker} trade",
                    rationale=f"{marker} rationale",
                    actions=[f"{marker} action"],
                    example_language=[f"{marker} example"],
                    success_indicator=f"{marker} indicator",
                )
            ],
            long_term_skills=[f"{marker} listening"],
            preparation_checklist=[f"{marker} checklist"],
            avoid_next_time=[f"{marker} avoid"],
            confidence="medium",
        ),
        created_at=datetime.now(UTC),
    )
    return debrief, strategy


def test_system_prompt_requires_cross_session_strict_json_memory() -> None:
    prompt = MemoryPromptBuilder().build_system_prompt()

    assert "cross-session patterns" in prompt
    assert "one isolated observation" in prompt
    assert "Do not invent evidence" in prompt
    assert "sessions_analyzed" in prompt
    assert "exact number of supplied sessions" in prompt
    assert "MUST return exactly one valid JSON object" in prompt
    assert "DO NOT wrap the JSON in Markdown or code fences" in prompt
    assert "do not include additional keys" in prompt
    assert prompt.rstrip().endswith("}")


def test_user_prompt_distinguishes_sessions_and_contains_only_artifacts() -> None:
    first = _create_records(
        UUID("00000000-0000-0000-0000-000000000001"),
        "First",
    )
    second = _create_records(
        UUID("00000000-0000-0000-0000-000000000002"),
        "Second",
    )

    prompt = MemoryPromptBuilder().build_user_prompt(
        [first[0], second[0]],
        [first[1], second[1]],
    )

    assert "Persisted artifacts from 2 negotiation sessions" in prompt
    assert "Session 1" in prompt
    assert "Session 2" in prompt
    assert str(first[0].session_id) in prompt
    assert str(second[0].session_id) in prompt
    assert first[0].debrief.overall_assessment in prompt
    assert second[0].debrief.recurring_risks[0] in prompt
    assert first[1].strategy.primary_objective in prompt
    assert second[1].strategy.prioritized_tactics[0].actions[0] in prompt
    assert "conversation turn" not in prompt.lower()
    assert "coach observation" not in prompt.lower()
    assert "scenario" not in prompt.lower()


def test_prompts_are_deterministic() -> None:
    records = _create_records(uuid4(), "Stable")
    builder = MemoryPromptBuilder()

    assert builder.build_system_prompt() == builder.build_system_prompt()
    assert builder.build_user_prompt(
        [records[0]],
        [records[1]],
    ) == builder.build_user_prompt(
        [records[0]],
        [records[1]],
    )
