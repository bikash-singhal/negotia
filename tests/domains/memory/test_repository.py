from datetime import UTC, datetime
from uuid import uuid4

from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.memory.repository import NegotiatorMemoryRepository


def _create_record(sessions_analyzed: int = 2) -> NegotiatorMemoryRecord:
    return NegotiatorMemoryRecord(
        id=uuid4(),
        memory=NegotiatorMemory(
            recurring_strengths=[],
            recurring_weaknesses=[],
            improving_skills=[],
            persistent_risks=[],
            priority_focus_areas=[],
            recommended_drills=[],
            sessions_analyzed=sessions_analyzed,
            confidence="low",
        ),
        source_session_ids=tuple(uuid4() for _ in range(sessions_analyzed)),
        created_at=datetime.now(UTC),
    )


def test_empty_repository_has_no_latest_record_or_versions() -> None:
    repository = NegotiatorMemoryRepository()

    assert repository.get_latest() is None
    assert repository.list_all() == []


def test_create_stores_returns_and_marks_record_as_latest() -> None:
    repository = NegotiatorMemoryRepository()
    record = _create_record()

    result = repository.create(record)

    assert result is record
    assert repository.get_latest() is record
    assert repository.list_all() == [record]


def test_new_version_preserves_older_immutable_record() -> None:
    repository = NegotiatorMemoryRepository()
    first = repository.create(_create_record(2))
    second = repository.create(_create_record(3))

    assert repository.list_all() == [first, second]
    assert repository.get_latest() is second
    assert first.memory.sessions_analyzed == 2
    assert second.memory.sessions_analyzed == 3


def test_list_all_returns_defensive_list_copy() -> None:
    repository = NegotiatorMemoryRepository()
    record = repository.create(_create_record())

    versions = repository.list_all()
    versions.clear()

    assert repository.list_all() == [record]
