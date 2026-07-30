from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.domains.coach.repository import CoachObservationRepository
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.memory.repository import NegotiatorMemoryRepository
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.opponent.profile_builder import OpponentProfileBuilder
from app.domains.scenario.repository import ScenarioRepository
from app.domains.scenario.service import ScenarioService
from app.domains.strategy.repository import NegotiationStrategyRepository
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider
from app.main import app
from app.prompts.coach import CoachPromptBuilder
from app.prompts.debrief import DebriefPromptBuilder
from app.prompts.memory import MemoryPromptBuilder
from app.prompts.negotiation_state import NegotiationStatePromptBuilder
from app.prompts.opponent import OpponentPromptBuilder
from app.prompts.strategy import StrategyPromptBuilder
from app.services.adaptive_context import AdaptiveContextService
from app.services.coach import CoachObservationExtractor, CoachService
from app.services.debrief import DebriefExtractor, DebriefService
from app.services.memory import MemoryExtractor, MemoryService
from app.services.negotiation_engine import NegotiationEngine
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentService
from app.services.strategy import StrategyExtractor, StrategyService


@dataclass(frozen=True)
class CompletionContext:
    negotiation_repository: NegotiationRepository
    negotiation_service: NegotiationService
    debrief_repository: NegotiationDebriefRepository
    debrief_service: DebriefService
    strategy_repository: NegotiationStrategyRepository
    strategy_service: StrategyService
    memory_repository: NegotiatorMemoryRepository
    memory_service: MemoryService
    artifact_provider: MagicMock


def _parse_uuid(value: object) -> UUID:
    assert isinstance(value, str)
    return UUID(value)


def _parse_datetime(value: object) -> datetime:
    assert isinstance(value, str)
    return datetime.fromisoformat(value)


@pytest.fixture
def completion_context() -> Iterator[CompletionContext]:
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
    )
    scenario_repository = ScenarioRepository()
    negotiation_repository = NegotiationRepository()
    turn_repository = NegotiationTurnRepository()
    coach_repository = CoachObservationRepository()
    debrief_repository = NegotiationDebriefRepository()
    strategy_repository = NegotiationStrategyRepository()
    memory_repository = NegotiatorMemoryRepository()
    fake_provider = FakeLLMProvider()
    artifact_provider = MagicMock(spec=LLMProvider, wraps=FakeLLMProvider())
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
        DebriefExtractor(
            DebriefPromptBuilder(),
            artifact_provider,
        ),
        debrief_repository,
    )
    strategy_service = StrategyService(
        debrief_repository,
        StrategyExtractor(
            StrategyPromptBuilder(),
            artifact_provider,
        ),
        strategy_repository,
    )
    memory_service = MemoryService(
        debrief_repository,
        strategy_repository,
        MemoryExtractor(
            MemoryPromptBuilder(),
            artifact_provider,
        ),
        memory_repository,
    )
    adaptive_context_service = AdaptiveContextService(memory_service)
    coach_service = CoachService(
        CoachObservationExtractor(
            CoachPromptBuilder(),
            fake_provider,
        ),
        coach_repository,
        adaptive_context_service,
    )
    opponent_service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        NegotiationStateExtractor(
            NegotiationStatePromptBuilder(),
            fake_provider,
        ),
        OpponentProfileBuilder(),
        OpponentPromptBuilder(),
        fake_provider,
        adaptive_context_service,
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
        negotiation_service,
        turn_service,
        debrief_service,
        strategy_service,
        memory_service,
    )
    try:
        yield CompletionContext(
            negotiation_repository=negotiation_repository,
            negotiation_service=negotiation_service,
            debrief_repository=debrief_repository,
            debrief_service=debrief_service,
            strategy_repository=strategy_repository,
            strategy_service=strategy_service,
            memory_repository=memory_repository,
            memory_service=memory_service,
            artifact_provider=artifact_provider,
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
        ) = original_services


@pytest.fixture
def client(completion_context: CompletionContext) -> Iterator[TestClient]:
    del completion_context
    with TestClient(app, raise_server_exceptions=False) as test_client:
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


def _create_session(client: TestClient) -> dict[str, object]:
    scenario_response = client.post(
        "/api/v1/scenarios",
        json=_valid_scenario_data(),
    )
    assert scenario_response.status_code == 201
    scenario = scenario_response.json()
    response = client.post(
        "/api/v1/negotiations",
        json={"scenario_id": scenario["scenario_id"]},
    )
    assert response.status_code == 201
    return response.json()


def _create_turn(
    client: TestClient,
    session_id: object,
    speaker: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/turns",
        json={
            "session_id": session_id,
            "speaker": speaker,
            "content": "We need a ten percent price reduction.",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_completed_exchange(client: TestClient) -> dict[str, object]:
    session = _create_session(client)
    _create_turn(client, session["id"], "user")
    response = client.post(f"/api/v1/negotiations/{session['id']}/opponent-response")
    assert response.status_code == 201
    return session


def _expected_strategy() -> dict[str, object]:
    return {
        "primary_objective": "Make concessions conditional on reciprocal value.",
        "expected_outcome": (
            "Each concession advances the user toward a balanced agreement."
        ),
        "prioritized_tactics": [
            {
                "priority": 1,
                "title": "Trade rather than concede",
                "rationale": "Conditional trades protect value.",
                "actions": ["Request reciprocal value for every concession."],
                "example_language": [
                    ("I can agree to that if you can improve the payment terms.")
                ],
                "success_indicator": ("Every concession receives reciprocal value."),
            },
            {
                "priority": 2,
                "title": "Prepare concession boundaries",
                "rationale": "Defined boundaries prevent reactive concessions.",
                "actions": ["Set concession limits before negotiating."],
                "example_language": ["That is the furthest I can move on price."],
                "success_indicator": "No unplanned concessions are made.",
            },
        ],
        "long_term_skills": ["Concession planning"],
        "preparation_checklist": ["Define reciprocal asks."],
        "avoid_next_time": ["Do not concede without receiving value."],
        "confidence": "low",
    }


def _expected_memory(session_count: int = 2) -> dict[str, object]:
    return {
        "recurring_strengths": ["Uses conditional concessions."],
        "recurring_weaknesses": ["Anchors before gathering information."],
        "improving_skills": ["Concession planning"],
        "persistent_risks": ["Makes unilateral concessions."],
        "priority_focus_areas": ["Diagnostic questioning"],
        "recommended_drills": ["Practice five discovery questions."],
        "sessions_analyzed": session_count,
        "confidence": "medium",
    }


def test_complete_negotiation_returns_structured_artifacts(
    client: TestClient,
) -> None:
    session = _create_completed_exchange(client)

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")
    body = response.json()

    assert response.status_code == 200
    assert set(body) == {
        "session_id",
        "status",
        "completed_at",
        "debrief",
        "observation_count",
        "debrief_id",
        "debrief_created_at",
        "strategy",
        "strategy_id",
        "strategy_created_at",
        "memory",
        "memory_id",
        "memory_created_at",
    }
    assert body["session_id"] == session["id"]
    assert body["status"] == "completed"
    assert _parse_datetime(body["completed_at"]).utcoffset() == timedelta(0)
    assert _parse_datetime(body["debrief_created_at"]).utcoffset() == timedelta(0)
    assert _parse_datetime(body["strategy_created_at"]).utcoffset() == timedelta(0)
    assert _parse_uuid(body["debrief_id"])
    assert _parse_uuid(body["strategy_id"])
    assert body["observation_count"] == 1
    assert body["debrief"] == {
        "repeated_strengths": [],
        "repeated_weaknesses": [],
        "key_missed_opportunities": [],
        "recurring_risks": [],
        "overall_assessment": (
            "There is not enough evidence for a detailed assessment."
        ),
        "confidence": "low",
    }
    assert body["strategy"] == _expected_strategy()
    assert body["memory"] is None
    assert body["memory_id"] is None
    assert body["memory_created_at"] is None
    assert "strategy_debrief_id" not in body

    session_response = client.get(f"/api/v1/negotiations/{session['id']}")
    assert session_response.status_code == 200
    persisted_session = session_response.json()
    assert persisted_session["status"] == "completed"
    assert persisted_session["updated_at"] == body["completed_at"]


def test_one_completed_exchange_is_sufficient(client: TestClient) -> None:
    session = _create_completed_exchange(client)

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert response.status_code == 200
    assert response.json()["observation_count"] == 1


def test_second_completion_returns_populated_memory_fields(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    first_session = _create_completed_exchange(client)
    first_response = client.post(f"/api/v1/negotiations/{first_session['id']}/complete")
    second_session = _create_completed_exchange(client)
    completion_context.artifact_provider.generate.reset_mock()

    response = client.post(f"/api/v1/negotiations/{second_session['id']}/complete")
    body = response.json()

    assert first_response.status_code == 200
    assert first_response.json()["memory"] is None
    assert response.status_code == 200
    assert body["memory"] == _expected_memory()
    assert _parse_uuid(body["memory_id"])
    assert _parse_datetime(body["memory_created_at"]).utcoffset() == timedelta(0)
    assert "trigger_session_id" not in body
    assert "source_session_ids" not in body
    memory_record = completion_context.memory_repository.get_by_trigger_session(
        _parse_uuid(second_session["id"])
    )
    assert memory_record is not None
    assert body["memory_id"] == str(memory_record.id)
    assert _parse_datetime(body["memory_created_at"]) == memory_record.created_at
    assert body["memory"] == memory_record.memory.model_dump(mode="json")
    assert completion_context.artifact_provider.generate.call_count == 3


def test_repeated_completion_returns_historical_memory_by_trigger(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    first_session = _create_completed_exchange(client)
    first_completion = client.post(
        f"/api/v1/negotiations/{first_session['id']}/complete"
    )
    second_session = _create_completed_exchange(client)
    second_completion = client.post(
        f"/api/v1/negotiations/{second_session['id']}/complete"
    )
    second_body = second_completion.json()
    completion_context.artifact_provider.generate.reset_mock()

    repeated_first = client.post(f"/api/v1/negotiations/{first_session['id']}/complete")
    repeated_second = client.post(
        f"/api/v1/negotiations/{second_session['id']}/complete"
    )

    assert first_completion.status_code == 200
    assert first_completion.json()["memory"] is None
    assert second_completion.status_code == 200
    assert repeated_first.status_code == 200
    assert repeated_first.json()["memory"] is None
    assert repeated_first.json()["memory_id"] is None
    assert repeated_first.json()["memory_created_at"] is None
    assert repeated_second.status_code == 200
    assert repeated_second.json()["memory"] == second_body["memory"]
    assert repeated_second.json()["memory_id"] == second_body["memory_id"]
    assert (
        repeated_second.json()["memory_created_at"] == second_body["memory_created_at"]
    )
    completion_context.artifact_provider.generate.assert_not_called()


def test_later_completion_creates_new_memory_version(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    first_session = _create_completed_exchange(client)
    client.post(f"/api/v1/negotiations/{first_session['id']}/complete")
    second_session = _create_completed_exchange(client)
    second_response = client.post(
        f"/api/v1/negotiations/{second_session['id']}/complete"
    )
    third_session = _create_completed_exchange(client)
    third_response = client.post(f"/api/v1/negotiations/{third_session['id']}/complete")

    assert second_response.status_code == 200
    assert third_response.status_code == 200
    second_memory_id = _parse_uuid(second_response.json()["memory_id"])
    third_memory_id = _parse_uuid(third_response.json()["memory_id"])
    assert second_memory_id != third_memory_id
    versions = completion_context.memory_repository.list_all()
    assert len(versions) == 2
    assert versions[0].id == second_memory_id
    assert versions[0].memory.sessions_analyzed == 2
    assert versions[1].id == third_memory_id
    assert versions[1].memory.sessions_analyzed == 3
    assert versions[0].source_session_ids == tuple(
        sorted(
            (
                _parse_uuid(first_session["id"]),
                _parse_uuid(second_session["id"]),
            ),
            key=str,
        )
    )


def test_completion_without_turns_returns_conflict(client: TestClient) -> None:
    session = _create_session(client)

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "http_error"
    assert "cannot be completed without turns" in response.json()["error"]["message"]


def test_abandoned_session_cannot_be_completed(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    session = _create_session(client)
    stored_session = completion_context.negotiation_repository.get(
        _parse_uuid(session["id"])
    )
    assert stored_session is not None
    stored_session.status = NegotiationStatus.ABANDONED

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "http_error"
    assert (
        "cannot transition from 'abandoned' to 'completed'"
        in (response.json()["error"]["message"])
    )
    completion_context.artifact_provider.generate.assert_not_called()


def test_completion_with_latest_user_turn_returns_conflict(
    client: TestClient,
) -> None:
    session = _create_session(client)
    _create_turn(client, session["id"], "user")

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "http_error"
    assert "latest turn is from the user" in response.json()["error"]["message"]


def test_completion_without_coach_observation_returns_conflict(
    client: TestClient,
) -> None:
    session = _create_session(client)
    _create_turn(client, session["id"], "user")
    _create_turn(client, session["id"], "opponent")

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "A debrief cannot be generated without coach observations.",
        }
    }


def test_completion_rejects_malformed_uuid(client: TestClient) -> None:
    response = client.post("/api/v1/negotiations/not-a-uuid/complete")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_completion_returns_not_found_for_missing_session(
    client: TestClient,
) -> None:
    session_id = UUID("d9428888-122b-4b8a-a257-c6f5336c1f9d")

    response = client.post(f"/api/v1/negotiations/{session_id}/complete")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": (f"Negotiation session with id '{session_id}' was not found."),
        }
    }


def test_debrief_failure_does_not_complete_session(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    session = _create_completed_exchange(client)
    completion_context.artifact_provider.generate.side_effect = RuntimeError(
        "Provider failed"
    )

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred",
        }
    }
    persisted_session = completion_context.negotiation_repository.get(
        _parse_uuid(session["id"])
    )
    assert persisted_session is not None
    assert persisted_session.status is NegotiationStatus.CREATED
    assert (
        completion_context.debrief_repository.get_by_session(persisted_session.id)
        is None
    )


def test_repeated_completion_is_idempotent(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    session = _create_completed_exchange(client)

    first_response = client.post(f"/api/v1/negotiations/{session['id']}/complete")
    first_body = first_response.json()
    second_response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json() == first_body
    assert completion_context.artifact_provider.generate.call_count == 2
    session_id = _parse_uuid(session["id"])
    debrief_record = completion_context.debrief_repository.get_by_session(session_id)
    strategy_record = completion_context.strategy_repository.get_by_session(session_id)
    assert debrief_record is not None
    assert strategy_record is not None
    assert debrief_record.id == _parse_uuid(first_body["debrief_id"])
    assert strategy_record.id == _parse_uuid(first_body["strategy_id"])
    persisted_session = completion_context.negotiation_repository.get(session_id)
    assert persisted_session is not None
    assert persisted_session.updated_at == _parse_datetime(first_body["completed_at"])


def test_completion_reuses_existing_debrief_and_generates_missing_strategy(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    session = _create_completed_exchange(client)
    session_id = _parse_uuid(session["id"])
    existing_record = completion_context.debrief_service.generate_for_session(
        session_id
    )
    completion_context.artifact_provider.generate.reset_mock()

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")
    body = response.json()

    assert response.status_code == 200
    assert body["debrief_id"] == str(existing_record.id)
    assert completion_context.artifact_provider.generate.call_count == 1
    assert (
        completion_context.debrief_repository.get_by_session(session_id)
        is existing_record
    )
    strategy_record = completion_context.strategy_repository.get_by_session(session_id)
    assert strategy_record is not None
    assert body["strategy_id"] == str(strategy_record.id)
    persisted_session = completion_context.negotiation_repository.get(session_id)
    assert persisted_session is not None
    assert persisted_session.status is NegotiationStatus.COMPLETED


def test_completion_reuses_existing_debrief_and_strategy_during_recovery(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    session = _create_completed_exchange(client)
    session_id = _parse_uuid(session["id"])
    debrief_record = completion_context.debrief_service.generate_for_session(session_id)
    strategy_record = completion_context.strategy_service.generate_for_session(
        session_id
    )
    completion_context.artifact_provider.generate.reset_mock()

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")
    body = response.json()

    assert response.status_code == 200
    assert body["debrief_id"] == str(debrief_record.id)
    assert body["strategy_id"] == str(strategy_record.id)
    completion_context.artifact_provider.generate.assert_not_called()
    assert (
        completion_context.debrief_repository.get_by_session(session_id)
        is debrief_record
    )
    assert (
        completion_context.strategy_repository.get_by_session(session_id)
        is strategy_record
    )
    persisted_session = completion_context.negotiation_repository.get(session_id)
    assert persisted_session is not None
    assert persisted_session.status is NegotiationStatus.COMPLETED


def test_strategy_failure_does_not_complete_session(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    session = _create_completed_exchange(client)
    session_id = _parse_uuid(session["id"])
    debrief_record = completion_context.debrief_service.generate_for_session(session_id)
    completion_context.artifact_provider.generate.reset_mock()
    completion_context.artifact_provider.generate.side_effect = RuntimeError(
        "Strategy provider failed"
    )

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred",
        }
    }
    persisted_session = completion_context.negotiation_repository.get(session_id)
    assert persisted_session is not None
    assert persisted_session.status is NegotiationStatus.CREATED
    assert (
        completion_context.debrief_repository.get_by_session(session_id)
        is debrief_record
    )
    assert completion_context.strategy_repository.get_by_session(session_id) is None


def test_memory_failure_preserves_artifacts_and_retry_reuses_them(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    first_session = _create_completed_exchange(client)
    first_completion = client.post(
        f"/api/v1/negotiations/{first_session['id']}/complete"
    )
    assert first_completion.status_code == 200
    second_session = _create_completed_exchange(client)
    second_session_id = _parse_uuid(second_session["id"])
    fake_provider = FakeLLMProvider()
    expected_error = RuntimeError("Memory provider failed")

    def fail_memory(
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        if system_prompt.startswith("You are an expert negotiation memory analyst"):
            raise expected_error
        return fake_provider.generate(system_prompt, user_prompt)

    completion_context.artifact_provider.generate.reset_mock()
    completion_context.artifact_provider.generate.side_effect = fail_memory

    failed_response = client.post(
        f"/api/v1/negotiations/{second_session['id']}/complete"
    )

    assert failed_response.status_code == 500
    persisted_session = completion_context.negotiation_repository.get(second_session_id)
    assert persisted_session is not None
    assert persisted_session.status is NegotiationStatus.CREATED
    debrief_record = completion_context.debrief_repository.get_by_session(
        second_session_id
    )
    strategy_record = completion_context.strategy_repository.get_by_session(
        second_session_id
    )
    assert debrief_record is not None
    assert strategy_record is not None
    assert (
        completion_context.memory_repository.get_by_trigger_session(second_session_id)
        is None
    )
    assert completion_context.artifact_provider.generate.call_count == 3

    completion_context.artifact_provider.generate.side_effect = None
    completion_context.artifact_provider.generate.reset_mock()
    retry_response = client.post(
        f"/api/v1/negotiations/{second_session['id']}/complete"
    )

    assert retry_response.status_code == 200
    assert (
        completion_context.debrief_repository.get_by_session(second_session_id)
        is debrief_record
    )
    assert (
        completion_context.strategy_repository.get_by_session(second_session_id)
        is strategy_record
    )
    assert retry_response.json()["memory"] == _expected_memory()
    assert completion_context.artifact_provider.generate.call_count == 1


def test_retry_after_status_failure_reuses_persisted_memory(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    first_session = _create_completed_exchange(client)
    first_completion = client.post(
        f"/api/v1/negotiations/{first_session['id']}/complete"
    )
    assert first_completion.status_code == 200
    second_session = _create_completed_exchange(client)
    second_session_id = _parse_uuid(second_session["id"])
    original_mark_completed = completion_context.negotiation_service.mark_completed
    mark_attempts = 0

    def fail_once(session_id: UUID) -> NegotiationSession:
        nonlocal mark_attempts
        mark_attempts += 1
        if mark_attempts == 1:
            raise RuntimeError("Status persistence failed")
        return original_mark_completed(session_id)

    completion_context.artifact_provider.generate.reset_mock()
    with patch.object(
        completion_context.negotiation_service,
        "mark_completed",
        side_effect=fail_once,
    ):
        failed_response = client.post(
            f"/api/v1/negotiations/{second_session['id']}/complete"
        )
        memory_record = completion_context.memory_repository.get_by_trigger_session(
            second_session_id
        )
        completion_context.artifact_provider.generate.reset_mock()
        retry_response = client.post(
            f"/api/v1/negotiations/{second_session['id']}/complete"
        )

    assert failed_response.status_code == 500
    assert memory_record is not None
    assert retry_response.status_code == 200
    assert retry_response.json()["memory_id"] == str(memory_record.id)
    assert len(completion_context.memory_repository.list_all()) == 1
    completion_context.artifact_provider.generate.assert_not_called()


def test_completed_session_without_debrief_returns_safe_internal_error(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    session = _create_session(client)
    stored_session = completion_context.negotiation_repository.get(
        _parse_uuid(session["id"])
    )
    assert stored_session is not None
    stored_session.status = NegotiationStatus.COMPLETED

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred",
        }
    }


def test_completed_session_without_strategy_returns_safe_internal_error(
    client: TestClient,
    completion_context: CompletionContext,
) -> None:
    session = _create_completed_exchange(client)
    session_id = _parse_uuid(session["id"])
    completion_context.debrief_service.generate_for_session(session_id)
    completion_context.artifact_provider.generate.reset_mock()
    stored_session = completion_context.negotiation_repository.get(session_id)
    assert stored_session is not None
    stored_session.status = NegotiationStatus.COMPLETED

    response = client.post(f"/api/v1/negotiations/{session['id']}/complete")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred",
        }
    }
    completion_context.artifact_provider.generate.assert_not_called()
    assert completion_context.strategy_repository.get_by_session(session_id) is None
