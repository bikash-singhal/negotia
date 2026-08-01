from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domains.debrief.exceptions import (
    NegotiationDebriefAlreadyExistsError,
)
from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.domains.debrief.repository import NegotiationDebriefRepository
from tests.ownership import TEST_USER_ID


def _create_record(session_id: UUID) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=NegotiationDebrief(
            repeated_strengths=[],
            repeated_weaknesses=[],
            key_missed_opportunities=[],
            recurring_risks=[],
            overall_assessment="Evidence is limited.",
            confidence="low",
        ),
        observation_count=1,
        created_at=datetime.now(UTC),
    )


def test_create_stores_and_returns_record_by_session() -> None:
    repository = NegotiationDebriefRepository()
    record = _create_record(uuid4())

    result = repository.create(record, TEST_USER_ID)

    assert result is record
    assert repository.get_by_session_for_user(record.session_id, TEST_USER_ID) is record


def test_get_by_session_returns_none_for_unknown_session() -> None:
    repository = NegotiationDebriefRepository()

    assert repository.get_by_session_for_user(uuid4(), TEST_USER_ID) is None


def test_duplicate_session_is_rejected_and_original_is_preserved() -> None:
    repository = NegotiationDebriefRepository()
    session_id = uuid4()
    original = repository.create(_create_record(session_id), TEST_USER_ID)
    duplicate = _create_record(session_id)

    with pytest.raises(NegotiationDebriefAlreadyExistsError) as exc_info:
        repository.create(duplicate, TEST_USER_ID)

    assert exc_info.value.session_id == session_id
    assert repository.get_by_session_for_user(session_id, TEST_USER_ID) is original
    assert repository.get_by_session_for_user(session_id, TEST_USER_ID) is not duplicate
