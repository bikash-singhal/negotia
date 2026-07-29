from collections.abc import Iterator
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.service import ScenarioService
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    scenario_repository = ScenarioRepository()
    negotiation_repository = NegotiationRepository()
    app.state.scenario_service = ScenarioService(scenario_repository)
    app.state.negotiation_service = NegotiationService(
        negotiation_repository,
        scenario_repository,
    )
    app.state.negotiation_turn_service = NegotiationTurnService(
        NegotiationTurnRepository(),
        negotiation_repository,
    )
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


def _create_scenario(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/scenarios", json=_valid_scenario_data())
    assert response.status_code == 201
    return response.json()


def _create_session(client: TestClient) -> dict[str, object]:
    scenario = _create_scenario(client)
    response = client.post(
        "/api/v1/negotiations",
        json={"scenario_id": scenario["scenario_id"]},
    )
    assert response.status_code == 201
    return response.json()


def _create_turn(
    client: TestClient,
    session_id: object,
    *,
    speaker: str = "user",
    content: str = "I propose a three-year agreement.",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/turns",
        json={
            "session_id": session_id,
            "speaker": speaker,
            "content": content,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_user_turn_returns_created(client: TestClient) -> None:
    session = _create_session(client)

    response = client.post(
        "/api/v1/turns",
        json={
            "session_id": session["id"],
            "speaker": "user",
            "content": "  I propose a three-year agreement.  ",
        },
    )
    turn = response.json()
    created_at = datetime.fromisoformat(turn["created_at"])

    assert response.status_code == 201
    assert UUID(turn["id"])
    assert turn["session_id"] == session["id"]
    assert turn["speaker"] == "user"
    assert turn["content"] == "I propose a three-year agreement."
    assert turn["turn_number"] == 1
    assert created_at.utcoffset() == timedelta(0)


def test_second_turn_gets_turn_number_two(client: TestClient) -> None:
    session = _create_session(client)
    first = _create_turn(client, session["id"])

    second = _create_turn(
        client,
        session["id"],
        speaker="opponent",
        content="I can consider that term.",
    )

    assert first["turn_number"] == 1
    assert second["turn_number"] == 2


def test_create_turn_rejects_unsupported_speaker(client: TestClient) -> None:
    session = _create_session(client)

    response = client.post(
        "/api/v1/turns",
        json={
            "session_id": session["id"],
            "speaker": "coach",
            "content": "Consider asking an open-ended question.",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_turn_rejects_blank_content(client: TestClient) -> None:
    session = _create_session(client)

    response = client.post(
        "/api/v1/turns",
        json={
            "session_id": session["id"],
            "speaker": "user",
            "content": "   ",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_turn_for_missing_session_returns_not_found(
    client: TestClient,
) -> None:
    session_id = uuid4()
    expected_message = f"Negotiation session with id '{session_id}' was not found."

    response = client.post(
        "/api/v1/turns",
        json={
            "session_id": str(session_id),
            "speaker": "user",
            "content": "I propose a three-year agreement.",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": expected_message,
        }
    }


def test_get_turn_returns_existing_turn(client: TestClient) -> None:
    session = _create_session(client)
    created = _create_turn(client, session["id"])

    response = client.get(f"/api/v1/turns/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_turn_returns_not_found(client: TestClient) -> None:
    turn_id = uuid4()

    response = client.get(f"/api/v1/turns/{turn_id}")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": f"Negotiation turn with id '{turn_id}' was not found.",
        }
    }


def test_get_turn_rejects_malformed_uuid(client: TestClient) -> None:
    response = client.get("/api/v1/turns/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_turns_returns_empty_list_for_existing_session(
    client: TestClient,
) -> None:
    session = _create_session(client)

    response = client.get(f"/api/v1/negotiations/{session['id']}/turns")

    assert response.status_code == 200
    assert response.json() == []


def test_list_turns_returns_turns_in_turn_number_order(
    client: TestClient,
) -> None:
    session = _create_session(client)
    first = _create_turn(client, session["id"])
    second = _create_turn(
        client,
        session["id"],
        speaker="opponent",
    )

    response = client.get(f"/api/v1/negotiations/{session['id']}/turns")

    assert response.status_code == 200
    assert response.json() == [first, second]


def test_list_turns_excludes_other_sessions(client: TestClient) -> None:
    session = _create_session(client)
    other_session = _create_session(client)
    expected = _create_turn(client, session["id"])
    _create_turn(client, other_session["id"])

    response = client.get(f"/api/v1/negotiations/{session['id']}/turns")

    assert response.status_code == 200
    assert response.json() == [expected]


def test_list_turns_for_missing_session_returns_not_found(
    client: TestClient,
) -> None:
    session_id = uuid4()
    expected_message = f"Negotiation session with id '{session_id}' was not found."

    response = client.get(f"/api/v1/negotiations/{session_id}/turns")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": expected_message,
        }
    }


def test_list_turns_rejects_malformed_session_uuid(client: TestClient) -> None:
    response = client.get("/api/v1/negotiations/not-a-uuid/turns")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
