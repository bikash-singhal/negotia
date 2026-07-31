from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.repositories.negotiation import (
    SQLNegotiationRepository,
    negotiation_to_domain,
    negotiation_to_model,
)
from app.database.repositories.scenario import SQLScenarioRepository
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.schemas import NegotiationSessionCreate
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError
from app.domains.scenario.models import Scenario, ScenarioDifficulty

from .conftest import SessionFactory


def _scenario() -> Scenario:
    return Scenario(
        title="Commercial lease renewal",
        description="Negotiate rent and renewal terms for an office lease.",
        industry="Commercial real estate",
        opponent_role="Property manager",
        objective="Secure stable rent and flexible renewal terms.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Direct and detail-oriented",
        negotiation_style="Competitive but professional",
    )


def _session(scenario_id: UUID) -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        scenario_id=scenario_id,
        status=NegotiationStatus.CREATED,
        created_at=now,
        updated_at=now,
    )


def _repositories(
    session_factory: SessionFactory,
) -> tuple[SQLScenarioRepository, SQLNegotiationRepository, Scenario]:
    scenario_repository = SQLScenarioRepository(session_factory)
    negotiation_repository = SQLNegotiationRepository(session_factory)
    scenario = scenario_repository.create(_scenario())
    return scenario_repository, negotiation_repository, scenario


def test_negotiation_mapping_round_trip() -> None:
    scenario_id = uuid4()
    session = _session(scenario_id)

    assert negotiation_to_domain(negotiation_to_model(session)) == session


def test_create_get_and_list_persist_negotiation(
    database_session_factory: SessionFactory,
) -> None:
    _, repository, scenario = _repositories(database_session_factory)
    session = _session(scenario.scenario_id)

    created = repository.create(session)

    assert created == session
    assert created is not session
    assert repository.get(session.id) == session
    assert repository.list() == [session]


def test_get_returns_none_for_missing_negotiation(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLNegotiationRepository(database_session_factory)

    assert repository.get(uuid4()) is None


def test_duplicate_negotiation_id_raises_and_rolls_back(
    database_session_factory: SessionFactory,
) -> None:
    _, repository, scenario = _repositories(database_session_factory)
    session = _session(scenario.scenario_id)
    repository.create(session)

    with pytest.raises(IntegrityError):
        repository.create(session)

    assert repository.get(session.id) == session


def test_foreign_key_violation_raises_and_rolls_back(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLNegotiationRepository(database_session_factory)

    with pytest.raises(IntegrityError):
        repository.create(_session(uuid4()))

    assert repository.list() == []


def test_update_persists_changes_for_a_fresh_repository_read(
    database_session_factory: SessionFactory,
) -> None:
    scenario_repository, negotiation_repository, scenario = _repositories(
        database_session_factory
    )
    service = NegotiationService(negotiation_repository, scenario_repository)
    created = service.create_session(
        NegotiationSessionCreate(scenario_id=scenario.scenario_id)
    )
    original_updated_at = created.updated_at

    completed = service.mark_completed(created.id)
    reloaded = SQLNegotiationRepository(database_session_factory).get(created.id)

    assert completed.status is NegotiationStatus.COMPLETED
    assert completed.updated_at > original_updated_at
    assert completed.updated_at.utcoffset() == timedelta(0)
    assert reloaded == completed


def test_update_rejects_a_missing_negotiation(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLNegotiationRepository(database_session_factory)
    session = _session(uuid4())

    with pytest.raises(NegotiationSessionNotFoundError) as exc_info:
        repository.update(session)

    assert exc_info.value.session_id == session.id
