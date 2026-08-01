from datetime import UTC, datetime
from uuid import uuid4

from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.scenario.repository import ScenarioRepository
from tests.ownership import TEST_USER_ID


def _create_scenario() -> Scenario:
    now = datetime.now(UTC)
    return Scenario(
        scenario_id=uuid4(),
        user_id=TEST_USER_ID,
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
        created_at=now,
        updated_at=now,
    )


def test_create_stores_and_returns_scenario() -> None:
    repository = ScenarioRepository()
    scenario = _create_scenario()

    created = repository.create(scenario)

    assert created is scenario
    assert repository.get_for_user(scenario.scenario_id, TEST_USER_ID) is scenario


def test_get_returns_existing_scenario() -> None:
    repository = ScenarioRepository()
    scenario = repository.create(_create_scenario())

    assert repository.get_for_user(scenario.scenario_id, TEST_USER_ID) is scenario


def test_get_returns_none_for_missing_scenario() -> None:
    repository = ScenarioRepository()

    assert repository.get_for_user(uuid4(), TEST_USER_ID) is None


def test_list_returns_all_stored_scenarios() -> None:
    repository = ScenarioRepository()
    first = repository.create(_create_scenario())
    second = repository.create(_create_scenario())

    assert repository.list_for_user(TEST_USER_ID) == [first, second]
