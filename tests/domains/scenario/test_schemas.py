import pytest
from pydantic import ValidationError

from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.scenario.schemas import (
    ScenarioCreate,
    ScenarioInternalResponse,
    ScenarioResponse,
)
from tests.ownership import TEST_USER_ID


def _valid_scenario_data() -> dict[str, object]:
    return {
        "title": "Supplier contract renewal",
        "description": "Renegotiate the annual supplier contract and delivery terms.",
        "industry": "Manufacturing",
        "opponent_role": "Supplier account director",
        "objective": "Secure improved pricing and delivery guarantees.",
        "difficulty": "intermediate",
        "constraints": ["Annual budget cannot increase"],
        "personality": "Analytical and cautious",
        "negotiation_style": "Collaborative",
        "hidden_context": ["The supplier recently lost a major client"],
        "walk_away_conditions": ["Price increase above five percent"],
    }


def _create_scenario() -> Scenario:
    return Scenario(
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
    )


def test_scenario_create_validates_valid_input() -> None:
    scenario = ScenarioCreate.model_validate(_valid_scenario_data())

    assert scenario.difficulty is ScenarioDifficulty.INTERMEDIATE
    assert scenario.constraints == ["Annual budget cannot increase"]


def test_scenario_create_rejects_invalid_difficulty() -> None:
    data = _valid_scenario_data()
    data["difficulty"] = "expert"

    with pytest.raises(ValidationError):
        ScenarioCreate.model_validate(data)


def test_scenario_response_excludes_hidden_context() -> None:
    response = ScenarioResponse.model_validate(_create_scenario())

    assert "hidden_context" not in response.model_dump()


def test_scenario_response_excludes_walk_away_conditions() -> None:
    response = ScenarioResponse.model_validate(_create_scenario())

    assert "walk_away_conditions" not in response.model_dump()


def test_scenario_internal_response_includes_private_fields() -> None:
    response = ScenarioInternalResponse.model_validate(_create_scenario())
    data = response.model_dump()

    assert data["hidden_context"] == ["The supplier recently lost a major client"]
    assert data["walk_away_conditions"] == ["Price increase above five percent"]
