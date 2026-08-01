from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domains.coach.exceptions import CoachObservationAlreadyExistsError
from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.coach.repository import CoachObservationRepository
from tests.ownership import TEST_USER_ID


def _create_record(
    session_id: UUID,
    *,
    user_turn_id: UUID | None = None,
    opponent_turn_id: UUID | None = None,
) -> CoachObservationRecord:
    return CoachObservationRecord(
        id=uuid4(),
        session_id=session_id,
        user_turn_id=user_turn_id or uuid4(),
        opponent_turn_id=opponent_turn_id or uuid4(),
        observation=CoachObservation(
            strengths=["Used a conditional trade."],
            weaknesses=[],
            missed_opportunities=[],
            risk_signals=[],
            confidence="high",
        ),
        created_at=datetime.now(UTC),
    )


def test_create_stores_and_returns_record() -> None:
    repository = CoachObservationRepository()
    record = _create_record(uuid4())

    result = repository.create(record, TEST_USER_ID)

    assert result is record
    assert repository.list_by_session_for_user(record.session_id, TEST_USER_ID) == [
        record
    ]
    assert result.observation is record.observation


def test_list_by_session_filters_records_and_preserves_creation_order() -> None:
    repository = CoachObservationRepository()
    session_id = uuid4()
    first = repository.create(_create_record(session_id), TEST_USER_ID)
    other = repository.create(_create_record(uuid4()), TEST_USER_ID)
    second = repository.create(_create_record(session_id), TEST_USER_ID)

    result = repository.list_by_session_for_user(session_id, TEST_USER_ID)

    assert result == [first, second]
    assert other not in result


def test_repository_is_append_only() -> None:
    repository = CoachObservationRepository()
    session_id = uuid4()
    record = repository.create(_create_record(session_id), TEST_USER_ID)

    returned_records = repository.list_by_session_for_user(session_id, TEST_USER_ID)
    returned_records.clear()

    assert repository.list_by_session_for_user(session_id, TEST_USER_ID) == [record]
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")


def test_duplicate_exchange_is_rejected() -> None:
    repository = CoachObservationRepository()
    session_id = uuid4()
    user_turn_id = uuid4()
    opponent_turn_id = uuid4()
    original = repository.create(
        _create_record(
            session_id,
            user_turn_id=user_turn_id,
            opponent_turn_id=opponent_turn_id,
        ),
        TEST_USER_ID,
    )
    duplicate = _create_record(
        session_id,
        user_turn_id=user_turn_id,
        opponent_turn_id=opponent_turn_id,
    )

    with pytest.raises(CoachObservationAlreadyExistsError) as exc_info:
        repository.create(duplicate, TEST_USER_ID)

    assert exc_info.value.user_turn_id == user_turn_id
    assert exc_info.value.opponent_turn_id == opponent_turn_id
    assert repository.list_by_session_for_user(session_id, TEST_USER_ID) == [original]
