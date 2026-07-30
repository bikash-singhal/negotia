from datetime import UTC, datetime, timedelta
from inspect import signature
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.negotiation.exceptions import (
    InvalidNegotiationStatusTransitionError,
    ScenarioNotFoundError,
)
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.schemas import NegotiationSessionCreate
from app.domains.negotiation.service import NegotiationService
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.scenario.repository import ScenarioRepository


def _create_stored_scenario(repository: ScenarioRepository) -> Scenario:
    return repository.create(
        Scenario(
            title="Supplier contract renewal",
            description="Renegotiate the annual supplier contract and delivery terms.",
            industry="Manufacturing",
            opponent_role="Supplier account director",
            objective="Secure improved pricing and delivery guarantees.",
            difficulty=ScenarioDifficulty.INTERMEDIATE,
            personality="Analytical and cautious",
            negotiation_style="Collaborative",
        )
    )


def _create_session(
    status: NegotiationStatus = NegotiationStatus.CREATED,
) -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        scenario_id=uuid4(),
        status=status,
        created_at=now,
        updated_at=now,
    )


def test_create_session_when_scenario_exists() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    scenario = _create_stored_scenario(scenario_repository)
    service = NegotiationService(negotiation_repository, scenario_repository)

    session = service.create_session(
        NegotiationSessionCreate(scenario_id=scenario.scenario_id)
    )

    assert isinstance(session.id, UUID)
    assert session.scenario_id == scenario.scenario_id
    assert session.status is NegotiationStatus.CREATED
    assert negotiation_repository.get(session.id) is session
    assert session.created_at.tzinfo is not None
    assert session.created_at.utcoffset() == timedelta(0)
    assert session.updated_at.tzinfo is not None
    assert session.updated_at.utcoffset() == timedelta(0)
    assert session.created_at == session.updated_at


def test_missing_scenario_raises_and_does_not_store_session() -> None:
    scenario_id = uuid4()
    stored_sessions = NegotiationRepository()
    negotiation_repository = MagicMock(
        spec=NegotiationRepository,
        wraps=stored_sessions,
    )
    scenario_repository = MagicMock(spec=ScenarioRepository)
    scenario_repository.get.return_value = None
    service = NegotiationService(
        negotiation_repository,
        scenario_repository,
    )

    with pytest.raises(ScenarioNotFoundError) as exc_info:
        service.create_session(NegotiationSessionCreate(scenario_id=scenario_id))

    assert exc_info.value.scenario_id == scenario_id
    assert str(exc_info.value) == f"Scenario with id '{scenario_id}' was not found."
    assert stored_sessions.list() == []
    scenario_repository.get.assert_called_once_with(scenario_id)
    negotiation_repository.create.assert_not_called()


def test_create_session_calls_repositories() -> None:
    stored_scenarios = ScenarioRepository()
    scenario = _create_stored_scenario(stored_scenarios)
    scenario_repository = MagicMock(
        spec=ScenarioRepository,
        wraps=stored_scenarios,
    )
    negotiation_repository = MagicMock(
        spec=NegotiationRepository,
        wraps=NegotiationRepository(),
    )
    service = NegotiationService(
        negotiation_repository,
        scenario_repository,
    )

    request = NegotiationSessionCreate(scenario_id=scenario.scenario_id)
    session = service.create_session(request)

    scenario_repository.get.assert_called_once_with(request.scenario_id)
    negotiation_repository.create.assert_called_once_with(session)


def test_get_session_delegates_to_negotiation_repository() -> None:
    negotiation_repository = MagicMock(spec=NegotiationRepository)
    scenario_repository = MagicMock(spec=ScenarioRepository)
    service = NegotiationService(negotiation_repository, scenario_repository)
    session = _create_session()
    negotiation_repository.get.return_value = session

    result = service.get_session(session.id)

    assert result is session
    negotiation_repository.get.assert_called_once_with(session.id)


def test_list_sessions_delegates_to_negotiation_repository() -> None:
    negotiation_repository = MagicMock(spec=NegotiationRepository)
    scenario_repository = MagicMock(spec=ScenarioRepository)
    service = NegotiationService(negotiation_repository, scenario_repository)
    sessions = [_create_session(), _create_session()]
    negotiation_repository.list.return_value = sessions

    result = service.list_sessions()

    assert result == sessions
    negotiation_repository.list.assert_called_once_with()


@pytest.mark.parametrize(
    "initial_status",
    [NegotiationStatus.CREATED, NegotiationStatus.ACTIVE],
)
def test_mark_completed_persists_valid_transition(
    initial_status: NegotiationStatus,
) -> None:
    negotiation_repository = NegotiationRepository()
    session = _create_session(initial_status)
    session.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
    original_updated_at = session.updated_at
    negotiation_repository.create(session)
    service = NegotiationService(
        negotiation_repository,
        MagicMock(spec=ScenarioRepository),
    )

    result = service.mark_completed(session.id)

    assert result is session
    assert result.status is NegotiationStatus.COMPLETED
    assert result.updated_at > original_updated_at
    assert result.updated_at.tzinfo is not None
    assert result.updated_at.utcoffset() == timedelta(0)
    assert negotiation_repository.get(session.id) is result


def test_mark_completed_is_idempotent_without_updating_timestamp() -> None:
    negotiation_repository = NegotiationRepository()
    session = _create_session(NegotiationStatus.COMPLETED)
    original_updated_at = session.updated_at
    negotiation_repository.create(session)
    service = NegotiationService(
        negotiation_repository,
        MagicMock(spec=ScenarioRepository),
    )

    result = service.mark_completed(session.id)

    assert result is session
    assert result.updated_at is original_updated_at


def test_mark_completed_rejects_abandoned_session() -> None:
    negotiation_repository = NegotiationRepository()
    session = negotiation_repository.create(
        _create_session(NegotiationStatus.ABANDONED)
    )
    service = NegotiationService(
        negotiation_repository,
        MagicMock(spec=ScenarioRepository),
    )

    with pytest.raises(InvalidNegotiationStatusTransitionError) as exc_info:
        service.mark_completed(session.id)

    assert exc_info.value.session_id == session.id
    assert exc_info.value.current_status is NegotiationStatus.ABANDONED
    assert exc_info.value.target_status is NegotiationStatus.COMPLETED
    assert session.status is NegotiationStatus.ABANDONED


def test_negotiation_service_has_no_debrief_or_llm_dependency() -> None:
    parameters = signature(NegotiationService.__init__).parameters

    assert "debrief_service" not in parameters
    assert "llm_provider" not in parameters
