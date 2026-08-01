from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.repositories.scenario import (
    SQLScenarioRepository,
    scenario_to_domain,
    scenario_to_model,
)
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from tests.ownership import TEST_USER_ID

from .conftest import SessionFactory


def _scenario() -> Scenario:
    now = datetime.now(UTC)
    return Scenario(
        scenario_id=uuid4(),
        user_id=TEST_USER_ID,
        title="Supplier renewal",
        description="Renegotiate supplier pricing and delivery commitments.",
        industry="Manufacturing",
        opponent_role="Supplier account director",
        objective="Improve pricing while preserving delivery reliability.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Analytical and cautious",
        negotiation_style="Collaborative",
        constraints=["Minimum twelve-month term"],
        hidden_context=["Quarterly target pressure"],
        walk_away_conditions=["No delivery guarantee"],
        created_at=now,
        updated_at=now,
    )


def test_scenario_mapping_round_trip_copies_mutable_fields() -> None:
    scenario = _scenario()

    mapped = scenario_to_domain(scenario_to_model(scenario))

    assert mapped == scenario
    assert mapped.constraints is not scenario.constraints
    assert mapped.hidden_context is not scenario.hidden_context
    assert mapped.walk_away_conditions is not scenario.walk_away_conditions


def test_create_get_and_list_persist_scenario(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLScenarioRepository(database_session_factory)
    scenario = _scenario()

    created = repository.create(scenario)

    assert created == scenario
    assert created is not scenario
    assert repository.get_for_user(scenario.scenario_id, TEST_USER_ID) == scenario
    assert repository.list_for_user(TEST_USER_ID) == [scenario]


def test_get_returns_none_for_missing_scenario(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLScenarioRepository(database_session_factory)

    assert repository.get_for_user(uuid4(), TEST_USER_ID) is None


def test_duplicate_scenario_id_raises_and_rolls_back(
    database_session_factory: SessionFactory,
) -> None:
    repository = SQLScenarioRepository(database_session_factory)
    scenario = _scenario()
    repository.create(scenario)

    with pytest.raises(IntegrityError):
        repository.create(scenario)

    assert repository.get_for_user(scenario.scenario_id, TEST_USER_ID) == scenario
