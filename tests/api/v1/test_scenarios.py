from collections.abc import Iterator
from datetime import datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.service import ScenarioService
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider
from app.main import app
from app.prompts.scenario import ScenarioPromptBuilder
from app.services.scenario import ScenarioGenerator
from tests.api.v1.authentication import authenticated_request
from tests.ownership import TEST_USER_ID


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.state.scenario_service = ScenarioService(
        ScenarioRepository(),
        ScenarioGenerator(ScenarioPromptBuilder(), FakeLLMProvider()),
    )
    with authenticated_request(), TestClient(app) as test_client:
        yield test_client


def _valid_scenario_data() -> dict[str, object]:
    return {
        "title": "Supplier contract renewal",
        "description": "Renegotiate the annual supplier contract and delivery terms.",
        "difficulty": "intermediate",
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
    for field in ("title", "description", "difficulty"):
        assert data[field] == request_data[field]
    assert data["industry"] == "Technology"
    assert data["opponent_role"] == "Recruiter"
    assert data["objective"]
    assert data["personality"]
    assert data["negotiation_style"]
    assert data["constraints"]


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


def test_create_scenario_rejects_user_id(client: TestClient) -> None:
    request_data = _valid_scenario_data()
    request_data["user_id"] = str(uuid4())

    response = client.post("/api/v1/scenarios", json=request_data)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("provider_response", ["", "not-json", "{}"])
def test_create_scenario_returns_safe_bad_gateway_for_invalid_generation(
    provider_response: str,
) -> None:
    repository = ScenarioRepository()
    provider = MagicMock(spec=LLMProvider)
    provider.generate.return_value = provider_response
    app.state.scenario_service = ScenarioService(
        repository,
        ScenarioGenerator(ScenarioPromptBuilder(), provider),
    )

    with authenticated_request(), TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/scenarios",
            json=_valid_scenario_data(),
        )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "http_error"
    assert "not-json" not in response.text
    assert repository.list_for_user(TEST_USER_ID) == []


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
