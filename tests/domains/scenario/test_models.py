from datetime import timedelta
from uuid import UUID

from app.domains.scenario.models import Scenario, ScenarioDifficulty


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


def test_scenario_generates_uuid() -> None:
    scenario = _create_scenario()

    assert isinstance(scenario.scenario_id, UUID)


def test_scenario_timestamps_are_timezone_aware_utc() -> None:
    scenario = _create_scenario()

    assert scenario.created_at.tzinfo is not None
    assert scenario.created_at.utcoffset() == timedelta(0)
    assert scenario.updated_at.tzinfo is not None
    assert scenario.updated_at.utcoffset() == timedelta(0)


def test_scenario_list_defaults_are_independent() -> None:
    first = _create_scenario()
    second = _create_scenario()

    assert first.constraints is not second.constraints
    assert first.hidden_context is not second.hidden_context
    assert first.walk_away_conditions is not second.walk_away_conditions
