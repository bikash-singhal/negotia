from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from tests.ownership import TEST_USER_ID


def _valid_memory_data() -> dict[str, object]:
    return {
        "stable_strengths": ["Uses conditional concessions."],
        "stable_weaknesses": ["Anchors before discovery."],
        "improving_skills": ["Active listening"],
        "persistent_risks": ["Makes unilateral concessions."],
        "highest_priority_skill": "Diagnostic questioning",
        "next_session_drill": "Practice five discovery questions.",
        "progress_summary": "Discovery is improving; anchoring needs work.",
        "sessions_analyzed": 2,
        "confidence": "medium",
    }


def test_negotiator_memory_validates_strict_complete_data() -> None:
    memory = NegotiatorMemory.model_validate(_valid_memory_data())

    assert memory.sessions_analyzed == 2
    assert memory.confidence == "medium"
    assert memory.stable_strengths == ["Uses conditional concessions."]


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


@pytest.mark.parametrize(
    ("field_name", "maximum"),
    [
        ("stable_strengths", 3),
        ("stable_weaknesses", 3),
        ("improving_skills", 2),
        ("persistent_risks", 2),
    ],
)
def test_negotiator_memory_enforces_bounded_lists(
    field_name: str,
    maximum: int,
) -> None:
    data = _valid_memory_data()
    data[field_name] = [f"Item {index}" for index in range(maximum + 1)]

    with pytest.raises(ValidationError):
        NegotiatorMemory.model_validate(data)


@pytest.mark.parametrize(
    "field_name",
    ["highest_priority_skill", "next_session_drill", "progress_summary"],
)
def test_negotiator_memory_requires_compact_coaching_text(field_name: str) -> None:
    data = _valid_memory_data()
    data.pop(field_name)

    with pytest.raises(ValidationError):
        NegotiatorMemory.model_validate(data)


def test_memory_record_is_immutable_and_stores_aware_timestamp() -> None:
    created_at = datetime.now(UTC)
    record = NegotiatorMemoryRecord(
        id=uuid4(),
        user_id=TEST_USER_ID,
        trigger_session_id=uuid4(),
        memory=NegotiatorMemory.model_validate(_valid_memory_data()),
        source_session_ids=(uuid4(), uuid4()),
        created_at=created_at,
    )

    assert record.created_at.utcoffset() == timedelta(0)
    assert record.trigger_session_id is not None
    timestamp_attribute = "created_at"
    with pytest.raises(FrozenInstanceError):
        setattr(record, timestamp_attribute, datetime.now(UTC))
