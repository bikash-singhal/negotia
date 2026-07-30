from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)


def test_negotiation_debrief_stores_every_structured_field() -> None:
    debrief = NegotiationDebrief(
        repeated_strengths=["Uses conditional trades consistently."],
        repeated_weaknesses=["Anchors before gathering enough information."],
        key_missed_opportunities=["Did not test the opponent's deadline."],
        recurring_risks=["Concedes without receiving value in return."],
        overall_assessment="The user negotiates constructively but concedes early.",
        confidence="high",
    )

    assert debrief.repeated_strengths == ["Uses conditional trades consistently."]
    assert debrief.repeated_weaknesses == [
        "Anchors before gathering enough information."
    ]
    assert debrief.key_missed_opportunities == ["Did not test the opponent's deadline."]
    assert debrief.recurring_risks == ["Concedes without receiving value in return."]
    assert debrief.overall_assessment == (
        "The user negotiates constructively but concedes early."
    )
    assert debrief.confidence == "high"


def test_record_composes_debrief_and_stores_metadata() -> None:
    debrief = NegotiationDebrief(
        repeated_strengths=[],
        repeated_weaknesses=[],
        key_missed_opportunities=[],
        recurring_risks=[],
        overall_assessment="Evidence is limited.",
        confidence="low",
    )
    session_id = uuid4()
    created_at = datetime.now(UTC)

    record = NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=debrief,
        observation_count=3,
        created_at=created_at,
    )

    assert record.session_id == session_id
    assert record.debrief is debrief
    assert record.observation_count == 3
    assert record.created_at is created_at
    assert record.created_at.tzinfo is not None
    assert record.created_at.utcoffset() == timedelta(0)
