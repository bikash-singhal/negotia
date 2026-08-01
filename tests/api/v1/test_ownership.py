from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.coach.repository import CoachObservationRepository
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.memory.repository import NegotiatorMemoryRepository
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.opponent.profile_builder import OpponentProfileBuilder
from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.service import ScenarioService
from app.domains.strategy.repository import NegotiationStrategyRepository
from app.domains.user.repository import UserRepository
from app.domains.user.service import UserService
from app.llm.fake import FakeLLMProvider
from app.main import app
from app.prompts.coach import CoachPromptBuilder
from app.prompts.debrief import DebriefPromptBuilder
from app.prompts.memory import MemoryPromptBuilder
from app.prompts.negotiation_state import NegotiationStatePromptBuilder
from app.prompts.opponent import OpponentPromptBuilder
from app.prompts.strategy import StrategyPromptBuilder
from app.security.passwords import PasswordHasher
from app.security.tokens import AccessTokenManager
from app.services.adaptive_context import AdaptiveContextService
from app.services.coach import CoachObservationExtractor, CoachService
from app.services.debrief import DebriefExtractor, DebriefService
from app.services.memory import MemoryExtractor, MemoryService
from app.services.negotiation_engine import NegotiationEngine
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentService
from app.services.strategy import StrategyExtractor, StrategyService
from app.workflows.completion.service import CompletionWorkflowService
from tests.workflows.completion.unit_of_work import (
    build_in_memory_unit_of_work_factory,
)


@dataclass(frozen=True)
class OwnershipContext:
    memory_repository: NegotiatorMemoryRepository
    adaptive_context_service: AdaptiveContextService


def _parse_uuid(value: object) -> UUID:
    assert isinstance(value, str)
    return UUID(value)


@pytest.fixture
def ownership_context() -> Iterator[OwnershipContext]:
    original_services = (
        app.state.scenario_service,
        app.state.negotiation_service,
        app.state.negotiation_turn_service,
        app.state.opponent_service,
        app.state.coach_service,
        app.state.debrief_service,
        app.state.strategy_service,
        app.state.memory_service,
        app.state.adaptive_context_service,
        app.state.negotiation_engine,
        app.state.user_service,
    )
    scenario_repository = ScenarioRepository()
    negotiation_repository = NegotiationRepository()
    turn_repository = NegotiationTurnRepository()
    coach_repository = CoachObservationRepository()
    debrief_repository = NegotiationDebriefRepository()
    strategy_repository = NegotiationStrategyRepository()
    memory_repository = NegotiatorMemoryRepository()
    provider = FakeLLMProvider()

    negotiation_service = NegotiationService(
        negotiation_repository,
        scenario_repository,
    )
    turn_service = NegotiationTurnService(
        turn_repository,
        negotiation_repository,
    )
    debrief_service = DebriefService(
        coach_repository,
        DebriefExtractor(DebriefPromptBuilder(), provider),
        debrief_repository,
    )
    strategy_service = StrategyService(
        debrief_repository,
        StrategyExtractor(StrategyPromptBuilder(), provider),
        strategy_repository,
    )
    memory_service = MemoryService(
        debrief_repository,
        strategy_repository,
        MemoryExtractor(MemoryPromptBuilder(), provider),
        memory_repository,
    )
    adaptive_context_service = AdaptiveContextService(memory_service)
    coach_service = CoachService(
        CoachObservationExtractor(CoachPromptBuilder(), provider),
        coach_repository,
        adaptive_context_service,
    )
    opponent_service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        NegotiationStateExtractor(NegotiationStatePromptBuilder(), provider),
        OpponentProfileBuilder(),
        OpponentPromptBuilder(),
        provider,
        adaptive_context_service,
    )
    completion_service = CompletionWorkflowService(
        negotiation_service,
        turn_service,
        debrief_service,
        strategy_service,
        memory_service,
        build_in_memory_unit_of_work_factory(
            negotiation_repository,
            debrief_repository,
            strategy_repository,
            memory_repository,
        ),
    )

    app.state.scenario_service = ScenarioService(scenario_repository)
    app.state.negotiation_service = negotiation_service
    app.state.negotiation_turn_service = turn_service
    app.state.opponent_service = opponent_service
    app.state.coach_service = coach_service
    app.state.debrief_service = debrief_service
    app.state.strategy_service = strategy_service
    app.state.memory_service = memory_service
    app.state.adaptive_context_service = adaptive_context_service
    app.state.negotiation_engine = NegotiationEngine(
        opponent_service,
        coach_service,
        completion_service,
    )
    app.state.user_service = UserService(
        UserRepository(),
        PasswordHasher(rounds=4),
        AccessTokenManager(
            "ownership-test-secret-at-least-32-bytes",
            expire_minutes=30,
        ),
    )

    try:
        yield OwnershipContext(
            memory_repository=memory_repository,
            adaptive_context_service=adaptive_context_service,
        )
    finally:
        (
            app.state.scenario_service,
            app.state.negotiation_service,
            app.state.negotiation_turn_service,
            app.state.opponent_service,
            app.state.coach_service,
            app.state.debrief_service,
            app.state.strategy_service,
            app.state.memory_service,
            app.state.adaptive_context_service,
            app.state.negotiation_engine,
            app.state.user_service,
        ) = original_services


@pytest.fixture
def client(ownership_context: OwnershipContext) -> Iterator[TestClient]:
    del ownership_context
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _scenario_payload(title: str = "Supplier contract renewal") -> dict[str, object]:
    return {
        "title": title,
        "description": "Renegotiate annual supplier pricing and delivery terms.",
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


def _register_and_login(
    client: TestClient,
    username: str,
) -> tuple[UUID, dict[str, str]]:
    password = "secure-password"
    registration = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    assert isinstance(access_token, str)
    return _parse_uuid(registration.json()["id"]), {
        "Authorization": f"Bearer {access_token}"
    }


def _create_scenario(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str = "Supplier contract renewal",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/scenarios",
        headers=headers,
        json=_scenario_payload(title),
    )
    assert response.status_code == 201
    return response.json()


def _create_session(
    client: TestClient,
    headers: dict[str, str],
    scenario_id: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/negotiations",
        headers=headers,
        json={"scenario_id": scenario_id},
    )
    assert response.status_code == 201
    return response.json()


def _create_completed_exchange(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str,
) -> dict[str, object]:
    scenario = _create_scenario(client, headers, title=title)
    session = _create_session(client, headers, scenario["scenario_id"])
    turn_response = client.post(
        "/api/v1/turns",
        headers=headers,
        json={
            "session_id": session["id"],
            "speaker": "user",
            "content": "We need a ten percent price reduction.",
        },
    )
    assert turn_response.status_code == 201
    opponent_response = client.post(
        f"/api/v1/negotiations/{session['id']}/opponent-response",
        headers=headers,
    )
    assert opponent_response.status_code == 201
    return session


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", "/api/v1/scenarios", None),
        ("POST", "/api/v1/scenarios", _scenario_payload()),
        ("GET", f"/api/v1/scenarios/{uuid4()}", None),
        ("GET", "/api/v1/negotiations", None),
        ("POST", "/api/v1/negotiations", {"scenario_id": str(uuid4())}),
        ("GET", f"/api/v1/negotiations/{uuid4()}", None),
        (
            "POST",
            "/api/v1/turns",
            {
                "session_id": str(uuid4()),
                "speaker": "user",
                "content": "A valid user position.",
            },
        ),
        ("GET", f"/api/v1/turns/{uuid4()}", None),
        ("GET", f"/api/v1/negotiations/{uuid4()}/turns", None),
        ("POST", f"/api/v1/negotiations/{uuid4()}/opponent-response", None),
        ("POST", f"/api/v1/negotiations/{uuid4()}/complete", None),
    ],
)
def test_business_endpoints_require_authentication(
    client: TestClient,
    method: str,
    path: str,
    json_body: dict[str, object] | None,
) -> None:
    response = client.request(method, path, json=json_body)

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Not authenticated",
        }
    }


def test_health_register_login_and_me_authentication_boundaries(
    client: TestClient,
) -> None:
    health = client.get("/api/v1/health")
    user_id, headers = _register_and_login(client, "public-user")
    me = client.get("/api/v1/auth/me", headers=headers)
    unauthorized_me = client.get("/api/v1/auth/me")

    assert health.status_code == 200
    assert me.status_code == 200
    assert _parse_uuid(me.json()["id"]) == user_id
    assert unauthorized_me.status_code == 401


def test_users_can_list_only_their_resources_and_cannot_access_foreign_resources(
    client: TestClient,
) -> None:
    _, user_a_headers = _register_and_login(client, "owner-a")
    _, user_b_headers = _register_and_login(client, "owner-b")
    scenario_a = _create_scenario(client, user_a_headers, title="Owner A scenario")
    scenario_b = _create_scenario(client, user_b_headers, title="Owner B scenario")
    session_a = _create_session(client, user_a_headers, scenario_a["scenario_id"])
    session_b = _create_session(client, user_b_headers, scenario_b["scenario_id"])
    turn_a_response = client.post(
        "/api/v1/turns",
        headers=user_a_headers,
        json={
            "session_id": session_a["id"],
            "speaker": "user",
            "content": "We need a ten percent price reduction.",
        },
    )
    assert turn_a_response.status_code == 201
    turn_a = turn_a_response.json()

    assert client.get("/api/v1/scenarios", headers=user_a_headers).json() == [
        scenario_a
    ]
    assert client.get("/api/v1/scenarios", headers=user_b_headers).json() == [
        scenario_b
    ]
    assert client.get("/api/v1/negotiations", headers=user_a_headers).json() == [
        session_a
    ]
    assert client.get("/api/v1/negotiations", headers=user_b_headers).json() == [
        session_b
    ]

    foreign_requests = [
        client.get(
            f"/api/v1/scenarios/{scenario_a['scenario_id']}",
            headers=user_b_headers,
        ),
        client.post(
            "/api/v1/negotiations",
            headers=user_b_headers,
            json={"scenario_id": scenario_a["scenario_id"]},
        ),
        client.get(
            f"/api/v1/negotiations/{session_a['id']}",
            headers=user_b_headers,
        ),
        client.post(
            "/api/v1/turns",
            headers=user_b_headers,
            json={
                "session_id": session_a["id"],
                "speaker": "user",
                "content": "Attempt to mutate another user's session.",
            },
        ),
        client.get(
            f"/api/v1/turns/{turn_a['id']}",
            headers=user_b_headers,
        ),
        client.get(
            f"/api/v1/negotiations/{session_a['id']}/turns",
            headers=user_b_headers,
        ),
        client.post(
            f"/api/v1/negotiations/{session_a['id']}/opponent-response",
            headers=user_b_headers,
        ),
        client.post(
            f"/api/v1/negotiations/{session_a['id']}/complete",
            headers=user_b_headers,
        ),
    ]

    assert all(response.status_code == 404 for response in foreign_requests)
    assert all(
        response.json()["error"]["code"] == "not_found" for response in foreign_requests
    )
    assert (
        client.get(
            f"/api/v1/scenarios/{scenario_a['scenario_id']}",
            headers=user_a_headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/negotiations/{session_a['id']}",
            headers=user_a_headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/turns/{turn_a['id']}",
            headers=user_a_headers,
        ).status_code
        == 200
    )


def test_foreign_and_nonexistent_ids_have_equivalent_public_behavior(
    client: TestClient,
) -> None:
    _, user_a_headers = _register_and_login(client, "enumeration-a")
    _, user_b_headers = _register_and_login(client, "enumeration-b")
    scenario = _create_scenario(client, user_a_headers)
    session = _create_session(client, user_a_headers, scenario["scenario_id"])

    foreign = client.get(
        f"/api/v1/negotiations/{session['id']}",
        headers=user_b_headers,
    )
    missing = client.get(
        f"/api/v1/negotiations/{uuid4()}",
        headers=user_b_headers,
    )

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["error"]["code"] == "not_found"
    assert missing.json()["error"]["code"] == "not_found"
    assert "not found" in foreign.json()["error"]["message"].lower()
    assert "not found" in missing.json()["error"]["message"].lower()


def test_request_bodies_cannot_select_resource_ownership(
    client: TestClient,
) -> None:
    user_id, headers = _register_and_login(client, "body-owner")
    scenario_payload = _scenario_payload()
    scenario_payload["user_id"] = str(user_id)

    scenario_response = client.post(
        "/api/v1/scenarios",
        headers=headers,
        json=scenario_payload,
    )
    negotiation_response = client.post(
        "/api/v1/negotiations",
        headers=headers,
        json={"scenario_id": str(uuid4()), "user_id": str(user_id)},
    )

    assert scenario_response.status_code == 422
    assert negotiation_response.status_code == 422
    assert scenario_response.json()["error"]["code"] == "validation_error"
    assert negotiation_response.json()["error"]["code"] == "validation_error"


def test_completion_and_memory_are_idempotent_and_isolated_by_user(
    client: TestClient,
    ownership_context: OwnershipContext,
) -> None:
    user_a_id, user_a_headers = _register_and_login(client, "memory-a")
    user_b_id, user_b_headers = _register_and_login(client, "memory-b")
    first_a = _create_completed_exchange(
        client,
        user_a_headers,
        title="Owner A first scenario",
    )
    second_a = _create_completed_exchange(
        client,
        user_a_headers,
        title="Owner A second scenario",
    )
    first_b = _create_completed_exchange(
        client,
        user_b_headers,
        title="Owner B first scenario",
    )

    assert (
        client.post(
            f"/api/v1/negotiations/{first_a['id']}/complete",
            headers=user_a_headers,
        ).status_code
        == 200
    )
    second_a_completion = client.post(
        f"/api/v1/negotiations/{second_a['id']}/complete",
        headers=user_a_headers,
    )
    first_b_completion = client.post(
        f"/api/v1/negotiations/{first_b['id']}/complete",
        headers=user_b_headers,
    )

    assert second_a_completion.status_code == 200
    assert second_a_completion.json()["memory_id"] is not None
    assert first_b_completion.status_code == 200
    assert first_b_completion.json()["memory"] is None
    assert ownership_context.memory_repository.get_latest(user_a_id) is not None
    assert ownership_context.memory_repository.get_latest(user_b_id) is None
    assert ownership_context.adaptive_context_service.get_context(user_a_id) is not None
    assert ownership_context.adaptive_context_service.get_context(user_b_id) is None

    repeated = client.post(
        f"/api/v1/negotiations/{second_a['id']}/complete",
        headers=user_a_headers,
    )

    assert repeated.status_code == 200
    assert repeated.json() == second_a_completion.json()
    assert len(ownership_context.memory_repository.list_for_user(user_a_id)) == 1
    assert ownership_context.memory_repository.list_for_user(user_b_id) == []
