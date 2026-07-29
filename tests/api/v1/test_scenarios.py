from collections.abc import Iterator
from datetime import datetime
from uuid import UUID, uuid4

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


def test_list_scenarios_returns_empty_list_initially(client: TestClient) -> None:
    response = client.get("/api/v1/scenarios")

    assert response.status_code == 200
    assert response.json() == []


def test_create_then_list_returns_created_scenario(client: TestClient) -> None:
    created = client.post(
        "/api/v1/scenarios",
        json=_valid_scenario_data(),
    ).json()

    response = client.get("/api/v1/scenarios")

    assert response.status_code == 200
    assert response.json() == [created]


def test_list_scenarios_returns_multiple_scenarios(client: TestClient) -> None:
    first_request = _valid_scenario_data()
    second_request = _valid_scenario_data()
    second_request["title"] = "Commercial lease renewal"

    first = client.post("/api/v1/scenarios", json=first_request).json()
    second = client.post("/api/v1/scenarios", json=second_request).json()

    response = client.get("/api/v1/scenarios")

    assert response.status_code == 200
    assert response.json() == [first, second]


def test_list_scenarios_excludes_private_fields(client: TestClient) -> None:
    client.post("/api/v1/scenarios", json=_valid_scenario_data())

    response = client.get("/api/v1/scenarios")
    scenario = response.json()[0]

    assert "hidden_context" not in scenario
    assert "walk_away_conditions" not in scenario


def test_get_scenario_returns_existing_scenario(client: TestClient) -> None:
    created = client.post(
        "/api/v1/scenarios",
        json=_valid_scenario_data(),
    ).json()

    response = client.get(f"/api/v1/scenarios/{created['scenario_id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_scenario_excludes_private_fields(client: TestClient) -> None:
    created = client.post(
        "/api/v1/scenarios",
        json=_valid_scenario_data(),
    ).json()

    response = client.get(f"/api/v1/scenarios/{created['scenario_id']}")
    scenario = response.json()

    assert "hidden_context" not in scenario
    assert "walk_away_conditions" not in scenario


def test_get_missing_scenario_returns_not_found(client: TestClient) -> None:
    scenario_id = uuid4()

    response = client.get(f"/api/v1/scenarios/{scenario_id}")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": f"Scenario with id '{scenario_id}' was not found.",
        }
    }


def test_get_scenario_rejects_malformed_uuid(client: TestClient) -> None:
    response = client.get("/api/v1/scenarios/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
