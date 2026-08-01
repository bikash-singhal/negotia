from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.schemas import ScenarioCreate, ScenarioGenerateRequest
from app.domains.scenario.service import ScenarioService
from app.llm.fake import FakeLLMProvider
from app.prompts.scenario import ScenarioPromptBuilder
from app.services.scenario import ScenarioGenerator
from tests.ownership import TEST_USER_ID


def _create_request() -> ScenarioCreate:
    return ScenarioCreate(
        title="Supplier contract renewal",
        description="Renegotiate the annual supplier contract and delivery terms.",
        industry="Manufacturing",
        opponent_role="Supplier account director",
        objective="Secure improved pricing and delivery guarantees.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        constraints=["Annual budget cannot increase"],
        personality="Analytical and cautious",
        negotiation_style="Collaborative",
        hidden_context=["The supplier recently lost a major client"],
        walk_away_conditions=["Price increase above five percent"],
    )


def _create_scenario() -> Scenario:
    now = datetime.now(UTC)
    request = _create_request()
    return Scenario(
        scenario_id=uuid4(),
        user_id=TEST_USER_ID,
        title=request.title,
        description=request.description,
        industry=request.industry,
        opponent_role=request.opponent_role,
        objective=request.objective,
        difficulty=request.difficulty,
        constraints=list(request.constraints),
        personality=request.personality,
        negotiation_style=request.negotiation_style,
        hidden_context=list(request.hidden_context),
        walk_away_conditions=list(request.walk_away_conditions),
        created_at=now,
        updated_at=now,
    )


def _generate_request() -> ScenarioGenerateRequest:
    return ScenarioGenerateRequest(
        title="Salary negotiation at Microsoft",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        description="Negotiate an improved compensation package professionally.",
    )


def _generator() -> ScenarioGenerator:
    return ScenarioGenerator(ScenarioPromptBuilder(), FakeLLMProvider())


def test_create_scenario_copies_mutable_lists() -> None:
    service = ScenarioService(ScenarioRepository())
    request = _create_request()

    scenario = service.create_scenario(request, TEST_USER_ID)

    assert scenario.constraints is not request.constraints
    assert scenario.hidden_context is not request.hidden_context
    assert scenario.walk_away_conditions is not request.walk_away_conditions


def test_create_scenario_maps_every_request_field() -> None:
    repository = ScenarioRepository()
    service = ScenarioService(repository)
    request = _create_request()

    scenario = service.create_scenario(request, TEST_USER_ID)

    assert scenario.title == request.title
    assert scenario.description == request.description
    assert scenario.industry == request.industry
    assert scenario.opponent_role == request.opponent_role
    assert scenario.objective == request.objective
    assert scenario.difficulty is request.difficulty
    assert scenario.constraints == request.constraints
    assert scenario.personality == request.personality
    assert scenario.negotiation_style == request.negotiation_style
    assert scenario.hidden_context == request.hidden_context
    assert scenario.walk_away_conditions == request.walk_away_conditions


def test_create_scenario_generates_uuid() -> None:
    service = ScenarioService(ScenarioRepository())

    scenario = service.create_scenario(_create_request(), TEST_USER_ID)

    assert isinstance(scenario.scenario_id, UUID)


def test_create_scenario_timestamps_are_timezone_aware() -> None:
    service = ScenarioService(ScenarioRepository())

    scenario = service.create_scenario(_create_request(), TEST_USER_ID)

    assert scenario.created_at.tzinfo is not None
    assert scenario.created_at.utcoffset() == timedelta(0)
    assert scenario.updated_at.tzinfo is not None
    assert scenario.updated_at.utcoffset() == timedelta(0)


def test_create_scenario_timestamps_are_equal_initially() -> None:
    service = ScenarioService(ScenarioRepository())

    scenario = service.create_scenario(_create_request(), TEST_USER_ID)

    assert scenario.created_at == scenario.updated_at


def test_create_scenario_is_stored_in_repository() -> None:
    repository = ScenarioRepository()
    service = ScenarioService(repository)

    scenario = service.create_scenario(_create_request(), TEST_USER_ID)

    assert repository.get_for_user(scenario.scenario_id, TEST_USER_ID) is scenario


def test_generate_scenario_preserves_user_input_and_ownership() -> None:
    repository = ScenarioRepository()
    service = ScenarioService(repository, _generator())
    request = _generate_request()

    scenario = service.generate_scenario(request, TEST_USER_ID)

    assert scenario.title == request.title
    assert scenario.description == request.description
    assert scenario.difficulty is request.difficulty
    assert scenario.user_id == TEST_USER_ID
    assert repository.get_for_user(scenario.scenario_id, TEST_USER_ID) is scenario


def test_generate_scenario_persists_every_generated_field() -> None:
    service = ScenarioService(ScenarioRepository(), _generator())

    scenario = service.generate_scenario(_generate_request(), TEST_USER_ID)

    assert scenario.industry == "Technology"
    assert scenario.opponent_role == "Recruiter"
    assert scenario.objective
    assert scenario.personality
    assert scenario.negotiation_style
    assert scenario.constraints
    assert scenario.hidden_context
    assert scenario.walk_away_conditions


def test_generate_scenario_does_not_persist_when_generation_fails() -> None:
    repository = ScenarioRepository()
    generator = MagicMock(spec=ScenarioGenerator)
    generator.generate.side_effect = RuntimeError("generation failed")
    service = ScenarioService(repository, generator)

    with pytest.raises(RuntimeError, match="generation failed"):
        service.generate_scenario(_generate_request(), TEST_USER_ID)

    assert repository.list_for_user(TEST_USER_ID) == []


def test_get_scenario_delegates_to_repository() -> None:
    repository = MagicMock(spec=ScenarioRepository)
    service = ScenarioService(repository)
    scenario = _create_scenario()
    repository.get_for_user.return_value = scenario

    result = service.get_scenario(scenario.scenario_id, TEST_USER_ID)

    assert result is scenario
    repository.get_for_user.assert_called_once_with(scenario.scenario_id, TEST_USER_ID)


def test_list_scenarios_delegates_to_repository() -> None:
    repository = MagicMock(spec=ScenarioRepository)
    service = ScenarioService(repository)
    scenarios = [_create_scenario(), _create_scenario()]
    repository.list_for_user.return_value = scenarios

    result = service.list_scenarios(TEST_USER_ID)

    assert result == scenarios
    repository.list_for_user.assert_called_once_with(TEST_USER_ID)
