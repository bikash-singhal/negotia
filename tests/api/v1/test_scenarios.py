from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.service import ScenarioService
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.state.scenario_service = ScenarioService(ScenarioRepository())
    with TestClient(app) as test_client:
        yield test_client


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


def test_create_scenario_returns_created(client: TestClient) -> None:
    response = client.post("/api/v1/scenarios", json=_valid_scenario_data())

    assert response.status_code == 201


def test_create_scenario_returns_all_public_fields(client: TestClient) -> None:
    request_data = _valid_scenario_data()

    response = client.post("/api/v1/scenarios", json=request_data)
    data = response.json()

    assert set(data) == {
        "scenario_id",
        "title",
        "description",
        "industry",
        "opponent_role",
        "objective",
        "difficulty",
        "constraints",
        "personality",
        "negotiation_style",
        "created_at",
        "updated_at",
    }
    for field in (
        "title",
        "description",
        "industry",
        "opponent_role",
        "objective",
        "difficulty",
        "constraints",
        "personality",
        "negotiation_style",
    ):
        assert data[field] == request_data[field]


def test_create_scenario_excludes_private_fields(client: TestClient) -> None:
    response = client.post("/api/v1/scenarios", json=_valid_scenario_data())
    data = response.json()

    assert "hidden_context" not in data
    assert "walk_away_conditions" not in data


def test_create_scenario_returns_uuid_and_timestamps(client: TestClient) -> None:
    response = client.post("/api/v1/scenarios", json=_valid_scenario_data())
    data = response.json()

    assert UUID(data["scenario_id"])
    assert datetime.fromisoformat(data["created_at"]).tzinfo is not None
    assert datetime.fromisoformat(data["updated_at"]).tzinfo is not None


def test_create_scenario_rejects_invalid_request(client: TestClient) -> None:
    request_data = _valid_scenario_data()
    request_data["difficulty"] = "expert"

    response = client.post("/api/v1/scenarios", json=request_data)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
