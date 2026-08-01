from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.memory.repository import NegotiatorMemoryRepository
from app.domains.strategy.repository import NegotiationStrategyRepository
from app.main import app
from app.services.memory import MemoryExtractor, MemoryService
from tests.api.v1.authentication import authenticated_request
from tests.ownership import OTHER_USER_ID, TEST_USER_ID


def _memory_record(user_id: UUID, priority: str) -> NegotiatorMemoryRecord:
    return NegotiatorMemoryRecord(
        id=uuid4(),
        user_id=user_id,
        trigger_session_id=uuid4(),
        memory=NegotiatorMemory(
            stable_strengths=["Uses conditional concessions."],
            stable_weaknesses=["Anchors before discovery."],
            improving_skills=["Diagnostic questioning"],
            persistent_risks=["Concedes without reciprocal value."],
            highest_priority_skill=priority,
            next_session_drill="Prepare three conditional trades.",
            progress_summary="Discovery is improving; concessions need work.",
            sessions_analyzed=2,
            confidence="medium",
        ),
        source_session_ids=(uuid4(), uuid4()),
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def memory_repository() -> Iterator[NegotiatorMemoryRepository]:
    repository = NegotiatorMemoryRepository()
    original_service = app.state.memory_service
    app.state.memory_service = MemoryService(
        MagicMock(spec=NegotiationDebriefRepository),
        MagicMock(spec=NegotiationStrategyRepository),
        MagicMock(spec=MemoryExtractor),
        repository,
    )
    try:
        yield repository
    finally:
        app.state.memory_service = original_service


@pytest.fixture
def client(
    memory_repository: NegotiatorMemoryRepository,
) -> Iterator[TestClient]:
    del memory_repository
    with authenticated_request(), TestClient(app) as test_client:
        yield test_client


def test_latest_memory_requires_authentication(
    memory_repository: NegotiatorMemoryRepository,
) -> None:
    del memory_repository
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/memory/latest")

    assert response.status_code == 401


def test_latest_memory_returns_documented_null_when_unavailable(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/memory/latest")

    assert response.status_code == 200
    assert response.json() is None


def test_latest_memory_returns_only_current_users_latest_record(
    client: TestClient,
    memory_repository: NegotiatorMemoryRepository,
) -> None:
    other_record = memory_repository.create(
        _memory_record(OTHER_USER_ID, "Other user's private priority")
    )
    older_record = memory_repository.create(
        _memory_record(TEST_USER_ID, "Diagnostic questioning")
    )
    latest_record = memory_repository.create(
        _memory_record(TEST_USER_ID, "Concession planning")
    )

    response = client.get("/api/v1/memory/latest")

    assert response.status_code == 200
    assert response.json() == latest_record.memory.model_dump(mode="json")
    assert response.json() != other_record.memory.model_dump(mode="json")
    assert memory_repository.list_for_user(TEST_USER_ID) == [
        older_record,
        latest_record,
    ]


def test_latest_memory_is_read_only(
    client: TestClient,
    memory_repository: NegotiatorMemoryRepository,
) -> None:
    record = memory_repository.create(
        _memory_record(TEST_USER_ID, "Concession planning")
    )

    first = client.get("/api/v1/memory/latest")
    second = client.get("/api/v1/memory/latest")

    assert first.json() == second.json()
    assert memory_repository.list_for_user(TEST_USER_ID) == [record]
