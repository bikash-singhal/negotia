from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domains.memory.exceptions import NegotiatorMemoryAlreadyExistsError
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.memory.repository import NegotiatorMemoryRepository
from tests.ownership import TEST_USER_ID


def _create_record(
    sessions_analyzed: int = 2,
    trigger_session_id: UUID | None = None,
) -> NegotiatorMemoryRecord:
    return NegotiatorMemoryRecord(
        id=uuid4(),
        user_id=TEST_USER_ID,
        trigger_session_id=trigger_session_id,
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

    assert repository.get_latest(TEST_USER_ID) is None
    assert repository.list_for_user(TEST_USER_ID) == []


def test_create_stores_returns_and_marks_record_as_latest() -> None:
    repository = NegotiatorMemoryRepository()
    record = _create_record()

    result = repository.create(record)

    assert result is record
    assert repository.get_latest(TEST_USER_ID) is record
    assert repository.list_for_user(TEST_USER_ID) == [record]


def test_new_version_preserves_older_immutable_record() -> None:
    repository = NegotiatorMemoryRepository()
    first = repository.create(_create_record(2))
    second = repository.create(_create_record(3))

    assert repository.list_for_user(TEST_USER_ID) == [first, second]
    assert repository.get_latest(TEST_USER_ID) is second
    assert first.memory.sessions_analyzed == 2
    assert second.memory.sessions_analyzed == 3


def test_list_all_returns_defensive_list_copy() -> None:
    repository = NegotiatorMemoryRepository()
    record = repository.create(_create_record())

    versions = repository.list_for_user(TEST_USER_ID)
    versions.clear()

    assert repository.list_for_user(TEST_USER_ID) == [record]


def test_get_by_trigger_session_returns_completion_record_only() -> None:
    repository = NegotiatorMemoryRepository()
    trigger_session_id = uuid4()
    standalone = repository.create(_create_record())
    completion_record = repository.create(
        _create_record(trigger_session_id=trigger_session_id)
    )

    assert (
        repository.get_by_trigger_session(trigger_session_id, TEST_USER_ID)
        is completion_record
    )
    assert (
        repository.get_by_trigger_session(
            standalone.source_session_ids[0], TEST_USER_ID
        )
        is None
    )


def test_duplicate_completion_trigger_is_rejected() -> None:
    repository = NegotiatorMemoryRepository()
    trigger_session_id = uuid4()
    original = repository.create(_create_record(trigger_session_id=trigger_session_id))

    with pytest.raises(NegotiatorMemoryAlreadyExistsError) as exc_info:
        repository.create(_create_record(trigger_session_id=trigger_session_id))

    assert exc_info.value.trigger_session_id == trigger_session_id
    assert (
        repository.get_by_trigger_session(trigger_session_id, TEST_USER_ID) is original
    )
    assert repository.list_for_user(TEST_USER_ID) == [original]


def test_multiple_standalone_versions_are_allowed() -> None:
    repository = NegotiatorMemoryRepository()
    first = repository.create(_create_record())
    second = repository.create(_create_record())

    assert repository.list_for_user(TEST_USER_ID) == [first, second]
    assert repository.get_latest(TEST_USER_ID) is second
