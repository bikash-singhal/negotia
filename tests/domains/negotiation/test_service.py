from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.negotiation.exceptions import ScenarioNotFoundError
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.schemas import NegotiationSessionCreate
from app.domains.negotiation.service import NegotiationService
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.scenario.repository import ScenarioRepository


def _create_scenario() -> Scenario:
    return Scenario(
        title="Supplier contract renewal",
        description="Renegotiate the annual supplier contract and delivery terms.",
        industry="Manufacturing",
        opponent_role="Supplier account director",
        objective="Secure improved pricing and delivery guarantees.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Analytical and cautious",
        negotiation_style="Collaborative",
    )


def _create_session() -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        scenario_id=uuid4(),
        status=NegotiationStatus.CREATED,
        created_at=now,
        updated_at=now,
    )


def test_create_session_when_scenario_exists() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    scenario = scenario_repository.create(_create_scenario())
    service = NegotiationService(negotiation_repository, scenario_repository)

    session = service.create_session(
        NegotiationSessionCreate(scenario_id=scenario.scenario_id)
    )

    assert isinstance(session.id, UUID)
    assert session.status is NegotiationStatus.CREATED
    assert session.created_at.tzinfo is not None
    assert session.created_at.utcoffset() == timedelta(0)
    assert session.created_at == session.updated_at


def test_created_session_contains_scenario_id() -> None:
    scenario_repository = ScenarioRepository()
    scenario = scenario_repository.create(_create_scenario())
    service = NegotiationService(NegotiationRepository(), scenario_repository)

    session = service.create_session(
        NegotiationSessionCreate(scenario_id=scenario.scenario_id)
    )

    assert session.scenario_id == scenario.scenario_id


def test_created_session_is_stored_in_negotiation_repository() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    scenario = scenario_repository.create(_create_scenario())
    service = NegotiationService(negotiation_repository, scenario_repository)

    session = service.create_session(
        NegotiationSessionCreate(scenario_id=scenario.scenario_id)
    )

    assert negotiation_repository.get(session.id) is session


def test_missing_scenario_raises_scenario_not_found_error() -> None:
    scenario_id = uuid4()
    service = NegotiationService(
        NegotiationRepository(),
        ScenarioRepository(),
    )

    with pytest.raises(ScenarioNotFoundError) as exc_info:
        service.create_session(NegotiationSessionCreate(scenario_id=scenario_id))

    assert exc_info.value.scenario_id == scenario_id
    assert str(exc_info.value) == f"Scenario with id '{scenario_id}' was not found."


def test_missing_scenario_does_not_store_session() -> None:
    negotiation_repository = NegotiationRepository()
    service = NegotiationService(
        negotiation_repository,
        ScenarioRepository(),
    )

    with pytest.raises(ScenarioNotFoundError):
        service.create_session(NegotiationSessionCreate(scenario_id=uuid4()))

    assert negotiation_repository.list() == []


def test_create_session_gets_scenario_with_correct_id() -> None:
    scenario = _create_scenario()
    scenario_repository = MagicMock(spec=ScenarioRepository)
    scenario_repository.get.return_value = scenario
    service = NegotiationService(
        NegotiationRepository(),
        scenario_repository,
    )

    service.create_session(
        NegotiationSessionCreate(scenario_id=scenario.scenario_id)
    )

    scenario_repository.get.assert_called_once_with(scenario.scenario_id)


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
