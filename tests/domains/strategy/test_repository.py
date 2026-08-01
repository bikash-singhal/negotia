from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domains.strategy.exceptions import (
    NegotiationStrategyAlreadyExistsError,
)
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
)
from app.domains.strategy.repository import NegotiationStrategyRepository
from tests.ownership import TEST_USER_ID


def _create_record(session_id: UUID) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=uuid4(),
        strategy=NegotiationStrategy(
            primary_objective="Protect value during concessions.",
            expected_outcome="Concessions produce reciprocal movement.",
            prioritized_tactics=[],
            long_term_skills=[],
            preparation_checklist=[],
            avoid_next_time=[],
            confidence="low",
        ),
        created_at=datetime.now(UTC),
    )


def test_create_stores_and_returns_strategy_by_session() -> None:
    repository = NegotiationStrategyRepository()
    record = _create_record(uuid4())

    result = repository.create(record, TEST_USER_ID)

    assert result is record
    assert repository.get_by_session_for_user(record.session_id, TEST_USER_ID) is record


def test_get_by_session_returns_none_for_unknown_session() -> None:
    repository = NegotiationStrategyRepository()

    assert repository.get_by_session_for_user(uuid4(), TEST_USER_ID) is None


def test_duplicate_session_is_rejected_and_original_is_preserved() -> None:
    repository = NegotiationStrategyRepository()
    session_id = uuid4()
    original = repository.create(_create_record(session_id), TEST_USER_ID)
    duplicate = _create_record(session_id)

    with pytest.raises(NegotiationStrategyAlreadyExistsError) as exc_info:
        repository.create(duplicate, TEST_USER_ID)

    assert exc_info.value.session_id == session_id
    assert repository.get_by_session_for_user(session_id, TEST_USER_ID) is original
    assert repository.get_by_session_for_user(session_id, TEST_USER_ID) is not duplicate


def test_repository_has_no_update_or_delete_operations() -> None:
    repository = NegotiationStrategyRepository()

    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")


def test_list_all_returns_all_records_as_defensive_copy() -> None:
    repository = NegotiationStrategyRepository()
    first = repository.create(_create_record(uuid4()), TEST_USER_ID)
    second = repository.create(_create_record(uuid4()), TEST_USER_ID)

    records = repository.list_for_user(TEST_USER_ID)
    records.clear()

    assert repository.list_for_user(TEST_USER_ID) == [first, second]
