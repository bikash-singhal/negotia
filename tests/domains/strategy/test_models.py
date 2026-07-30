from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
    NegotiationTactic,
)


def _create_strategy() -> NegotiationStrategy:
    return NegotiationStrategy(
        primary_objective="Make every concession conditional.",
        expected_outcome="Every concession receives reciprocal value.",
        prioritized_tactics=[
            NegotiationTactic(
                priority=1,
                title="Trade rather than concede",
                rationale="Conditional trades protect value.",
                actions=["Request reciprocal value."],
                example_language=["I can agree to that if you improve payment terms."],
                success_indicator="Every concession receives something in return.",
            )
        ],
        long_term_skills=["Concession planning"],
        preparation_checklist=["Define reciprocal asks."],
        avoid_next_time=["Do not make unilateral concessions."],
        confidence="high",
    )


def test_negotiation_strategy_stores_complete_recommendation() -> None:
    strategy = _create_strategy()

    assert strategy.primary_objective == "Make every concession conditional."
    assert strategy.expected_outcome == ("Every concession receives reciprocal value.")
    assert strategy.prioritized_tactics[0].priority == 1
    assert strategy.prioritized_tactics[0].example_language == [
        "I can agree to that if you improve payment terms."
    ]
    assert strategy.long_term_skills == ["Concession planning"]
    assert strategy.preparation_checklist == ["Define reciprocal asks."]
    assert strategy.avoid_next_time == ["Do not make unilateral concessions."]
    assert strategy.confidence == "high"


def test_strategy_record_composes_strategy_and_stores_metadata() -> None:
    strategy = _create_strategy()
    session_id = uuid4()
    debrief_id = uuid4()
    created_at = datetime.now(UTC)

    record = NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=debrief_id,
        strategy=strategy,
        created_at=created_at,
    )

    assert record.session_id == session_id
    assert record.debrief_id == debrief_id
    assert record.strategy is strategy
    assert record.created_at is created_at
    assert record.created_at.tzinfo is not None
    assert record.created_at.utcoffset() == timedelta(0)
