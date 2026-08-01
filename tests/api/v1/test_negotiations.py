from collections.abc import Iterator
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.service import NegotiationService
from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.service import ScenarioService
from app.llm.fake import FakeLLMProvider
from app.main import app
from app.prompts.scenario import ScenarioPromptBuilder
from app.services.scenario import ScenarioGenerator
from tests.api.v1.authentication import authenticated_request


@pytest.fixture
def client() -> Iterator[TestClient]:
    scenario_repository = ScenarioRepository()
    app.state.scenario_service = ScenarioService(
        scenario_repository,
        ScenarioGenerator(ScenarioPromptBuilder(), FakeLLMProvider()),
    )
    app.state.negotiation_service = NegotiationService(
        NegotiationRepository(),
        scenario_repository,
    )
    with authenticated_request(), TestClient(app) as test_client:
        yield test_client


def _valid_scenario_data() -> dict[str, object]:
    return {
        "title": "Supplier contract renewal",
        "description": "Renegotiate the annual supplier contract and delivery terms.",
        "difficulty": "intermediate",
    }


def _create_scenario(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/scenarios", json=_valid_scenario_data())
    assert response.status_code == 201
    return response.json()


def _create_negotiation(
    client: TestClient,
    scenario_id: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/negotiations",
        json={"scenario_id": scenario_id},
    )
    assert response.status_code == 201
    return response.json()


def test_create_negotiation_returns_created_session(client: TestClient) -> None:
    scenario = _create_scenario(client)

    response = client.post(
        "/api/v1/negotiations",
        json={"scenario_id": scenario["scenario_id"]},
    )
    session = response.json()
    created_at = datetime.fromisoformat(session["created_at"])
    updated_at = datetime.fromisoformat(session["updated_at"])

    assert response.status_code == 201
    assert UUID(session["id"])
    assert session["scenario_id"] == scenario["scenario_id"]
    assert session["status"] == "created"
    assert created_at.utcoffset() == timedelta(0)
    assert updated_at.utcoffset() == timedelta(0)
    assert created_at == updated_at


def test_create_negotiation_for_missing_scenario_returns_not_found(
    client: TestClient,
) -> None:
    scenario_id = uuid4()

    response = client.post(
        "/api/v1/negotiations",
        json={"scenario_id": str(scenario_id)},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": f"Scenario with id '{scenario_id}' was not found.",
        }
    }


def test_create_negotiation_rejects_invalid_request(client: TestClient) -> None:
    response = client.post("/api/v1/negotiations", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_negotiations_returns_empty_list_initially(client: TestClient) -> None:
    response = client.get("/api/v1/negotiations")

    assert response.status_code == 200
    assert response.json() == []


def test_created_negotiation_appears_in_list(client: TestClient) -> None:
    scenario = _create_scenario(client)
    created = _create_negotiation(client, scenario["scenario_id"])

    response = client.get("/api/v1/negotiations")

    assert response.status_code == 200
    assert response.json() == [created]


def test_list_negotiations_returns_multiple_sessions(client: TestClient) -> None:
    scenario = _create_scenario(client)
    first = _create_negotiation(client, scenario["scenario_id"])
    second = _create_negotiation(client, scenario["scenario_id"])

    response = client.get("/api/v1/negotiations")

    assert response.status_code == 200
    assert response.json() == [first, second]


def test_get_negotiation_returns_existing_session(client: TestClient) -> None:
    scenario = _create_scenario(client)
    created = _create_negotiation(client, scenario["scenario_id"])

    response = client.get(f"/api/v1/negotiations/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_negotiation_returns_not_found(client: TestClient) -> None:
    session_id = uuid4()
    expected_message = f"Negotiation session with id '{session_id}' was not found."

    response = client.get(f"/api/v1/negotiations/{session_id}")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": expected_message,
        }
    }


def test_get_negotiation_rejects_malformed_uuid(client: TestClient) -> None:
    response = client.get("/api/v1/negotiations/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
