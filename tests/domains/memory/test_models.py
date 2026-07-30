from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord


def _valid_memory_data() -> dict[str, object]:
    return {
        "recurring_strengths": ["Uses conditional concessions."],
        "recurring_weaknesses": ["Anchors before discovery."],
        "improving_skills": ["Active listening"],
        "persistent_risks": ["Makes unilateral concessions."],
        "priority_focus_areas": ["Diagnostic questioning"],
        "recommended_drills": ["Practice five discovery questions."],
        "sessions_analyzed": 2,
        "confidence": "medium",
    }


def test_negotiator_memory_validates_strict_complete_data() -> None:
    memory = NegotiatorMemory.model_validate(_valid_memory_data())

    assert memory.sessions_analyzed == 2
    assert memory.confidence == "medium"
    assert memory.recurring_strengths == ["Uses conditional concessions."]


def test_negotiator_memory_rejects_extra_fields() -> None:
    data = _valid_memory_data()
    data["unexpected"] = "value"

    with pytest.raises(ValidationError):
        NegotiatorMemory.model_validate(data)


@pytest.mark.parametrize("sessions_analyzed", [0, -1, "2"])
def test_negotiator_memory_rejects_invalid_session_counts(
    sessions_analyzed: object,
) -> None:
    data = _valid_memory_data()
    data["sessions_analyzed"] = sessions_analyzed

    with pytest.raises(ValidationError):
        NegotiatorMemory.model_validate(data)


def test_memory_record_is_immutable_and_stores_aware_timestamp() -> None:
    created_at = datetime.now(UTC)
    record = NegotiatorMemoryRecord(
        id=uuid4(),
        memory=NegotiatorMemory.model_validate(_valid_memory_data()),
        source_session_ids=(uuid4(), uuid4()),
        created_at=created_at,
    )

    assert record.created_at.utcoffset() == timedelta(0)
    timestamp_attribute = "created_at"
    with pytest.raises(FrozenInstanceError):
        setattr(record, timestamp_attribute, datetime.now(UTC))
