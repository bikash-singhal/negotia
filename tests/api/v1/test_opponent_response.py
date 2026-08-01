import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

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
from app.prompts.scenario import ScenarioPromptBuilder
from app.prompts.strategy import StrategyPromptBuilder
from app.services.adaptive_context import AdaptiveContextService
from app.services.coach import CoachObservationExtractor, CoachService
from app.services.debrief import DebriefExtractor, DebriefService
from app.services.memory import MemoryExtractor, MemoryService
from app.services.negotiation_engine import NegotiationEngine
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentService
from app.services.scenario import ScenarioGenerator
from app.services.strategy import StrategyExtractor, StrategyService
from app.workflows.completion.service import CompletionWorkflowService
from tests.api.v1.authentication import TEST_USER, authenticated_request
from tests.workflows.completion.unit_of_work import (
    build_in_memory_unit_of_work_factory,
)

FAKE_RESPONSE = (
    "I understand your position, but those terms are difficult for us to accept."
)
Repositories = tuple[
    ScenarioRepository,
    NegotiationRepository,
    NegotiationTurnRepository,
]


def _parse_uuid(value: object) -> UUID:
    assert isinstance(value, str)
    return UUID(value)


def _build_state_extractor() -> NegotiationStateExtractor:
    return NegotiationStateExtractor(
        NegotiationStatePromptBuilder(),
        FakeLLMProvider(),
    )


def _build_coach_service(
    repository: CoachObservationRepository,
    adaptive_context_service: AdaptiveContextService,
) -> CoachService:
    return CoachService(
        CoachObservationExtractor(
            CoachPromptBuilder(),
            FakeLLMProvider(),
        ),
        repository,
        adaptive_context_service,
    )


def _build_artifact_services(
    coach_repository: CoachObservationRepository,
) -> tuple[DebriefService, StrategyService, MemoryService]:
    debrief_repository = NegotiationDebriefRepository()
    debrief_service = DebriefService(
        coach_repository,
        DebriefExtractor(
            DebriefPromptBuilder(),
            FakeLLMProvider(),
        ),
        debrief_repository,
    )
    strategy_repository = NegotiationStrategyRepository()
    strategy_service = StrategyService(
        debrief_repository,
        StrategyExtractor(
            StrategyPromptBuilder(),
            FakeLLMProvider(),
        ),
        strategy_repository,
    )
    memory_service = MemoryService(
        debrief_repository,
        strategy_repository,
        MemoryExtractor(
            MemoryPromptBuilder(),
            FakeLLMProvider(),
        ),
        NegotiatorMemoryRepository(),
    )
    return debrief_service, strategy_service, memory_service


@pytest.fixture
def repositories() -> Repositories:
    return (
        ScenarioRepository(),
        NegotiationRepository(),
        NegotiationTurnRepository(),
    )


@pytest.fixture
def coach_repository() -> CoachObservationRepository:
    return CoachObservationRepository()


@pytest.fixture
def client(
    repositories: Repositories,
    coach_repository: CoachObservationRepository,
) -> Iterator[TestClient]:
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
    scenario_repository, negotiation_repository, turn_repository = repositories
    app.state.scenario_service = ScenarioService(
        scenario_repository,
        ScenarioGenerator(ScenarioPromptBuilder(), FakeLLMProvider()),
    )
    negotiation_service = NegotiationService(
        negotiation_repository,
        scenario_repository,
    )
    app.state.negotiation_service = negotiation_service
    negotiation_turn_service = NegotiationTurnService(
        turn_repository,
        negotiation_repository,
    )
    app.state.negotiation_turn_service = negotiation_turn_service
    debrief_service, strategy_service, memory_service = _build_artifact_services(
        coach_repository
    )
    adaptive_context_service = AdaptiveContextService(memory_service)
    coach_service = _build_coach_service(
        coach_repository,
        adaptive_context_service,
    )
    opponent_service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        _build_state_extractor(),
        OpponentProfileBuilder(),
        OpponentPromptBuilder(),
        FakeLLMProvider(),
        adaptive_context_service,
    )
    app.state.opponent_service = opponent_service
    app.state.coach_service = coach_service
    app.state.debrief_service = debrief_service
    app.state.strategy_service = strategy_service
    app.state.memory_service = memory_service
    app.state.adaptive_context_service = adaptive_context_service
    completion_workflow_service = CompletionWorkflowService(
        negotiation_service,
        negotiation_turn_service,
        debrief_service,
        strategy_service,
        memory_service,
        build_in_memory_unit_of_work_factory(
            negotiation_repository,
            debrief_service._debrief_repository,
            strategy_service._strategy_repository,
            memory_service._memory_repository,
        ),
    )
    app.state.negotiation_engine = NegotiationEngine(
        opponent_service,
        coach_service,
        completion_workflow_service,
    )
    try:
        with authenticated_request(), TestClient(app) as test_client:
            yield test_client
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


def _stream_events(response_text: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in response_text.splitlines() if line]


def _replace_opponent_provider(
    repositories: Repositories,
    coach_repository: CoachObservationRepository,
    provider: LLMProvider,
) -> None:
    scenario_repository, negotiation_repository, turn_repository = repositories
    negotiation_service = NegotiationService(
        negotiation_repository,
        scenario_repository,
    )
    negotiation_turn_service = NegotiationTurnService(
        turn_repository,
        negotiation_repository,
    )
    debrief_service, strategy_service, memory_service = _build_artifact_services(
        coach_repository
    )
    adaptive_context_service = AdaptiveContextService(memory_service)
    coach_service = _build_coach_service(
        coach_repository,
        adaptive_context_service,
    )
    opponent_service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        _build_state_extractor(),
        OpponentProfileBuilder(),
        OpponentPromptBuilder(),
        provider,
        adaptive_context_service,
    )
    app.state.opponent_service = opponent_service
    app.state.coach_service = coach_service
    app.state.negotiation_service = negotiation_service
    app.state.negotiation_turn_service = negotiation_turn_service
    app.state.debrief_service = debrief_service
    app.state.strategy_service = strategy_service
    app.state.memory_service = memory_service
    app.state.adaptive_context_service = adaptive_context_service
    completion_workflow_service = CompletionWorkflowService(
        negotiation_service,
        negotiation_turn_service,
        debrief_service,
        strategy_service,
        memory_service,
        build_in_memory_unit_of_work_factory(
            negotiation_repository,
            debrief_service._debrief_repository,
            strategy_service._strategy_repository,
            memory_service._memory_repository,
        ),
    )
    app.state.negotiation_engine = NegotiationEngine(
        opponent_service,
        coach_service,
        completion_workflow_service,
    )


def test_complete_http_workflow_generates_and_lists_opponent_turn(
    client: TestClient,
    coach_repository: CoachObservationRepository,
) -> None:
    session = _create_session(client)
    user_turn = _create_turn(client, session["id"])

    response = client.post(f"/api/v1/negotiations/{session['id']}/opponent-response")
    opponent_turn = response.json()

    assert response.status_code == 201
    assert set(opponent_turn) == {
        "id",
        "session_id",
        "speaker",
        "content",
        "turn_number",
        "created_at",
    }
    assert _parse_uuid(opponent_turn["id"])
    assert opponent_turn["session_id"] == session["id"]
    assert opponent_turn["speaker"] == "opponent"
    assert opponent_turn["content"] == FAKE_RESPONSE
    user_turn_number = user_turn["turn_number"]
    assert isinstance(user_turn_number, int)

    assert opponent_turn["turn_number"] == user_turn_number + 1

    history_response = client.get(f"/api/v1/negotiations/{session['id']}/turns")
    assert history_response.status_code == 200
    assert history_response.json() == [user_turn, opponent_turn]
    assert [
        (turn["turn_number"], turn["speaker"]) for turn in history_response.json()
    ] == [(1, "user"), (2, "opponent")]
    records = coach_repository.list_by_session_for_user(
        _parse_uuid(session["id"]), TEST_USER.id
    )
    assert len(records) == 1
    assert records[0].user_turn_id == _parse_uuid(user_turn["id"])
    assert records[0].opponent_turn_id == _parse_uuid(opponent_turn["id"])


def test_opponent_response_rejects_malformed_session_uuid(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/negotiations/not-a-uuid/opponent-response")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_opponent_response_returns_not_found_for_missing_session(
    client: TestClient,
) -> None:
    session_id = uuid4()
    expected_message = f"Negotiation session with id '{session_id}' was not found."

    response = client.post(f"/api/v1/negotiations/{session_id}/opponent-response")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": expected_message,
        }
    }


def test_opponent_response_returns_not_found_for_missing_scenario(
    client: TestClient,
    repositories: Repositories,
) -> None:
    _, negotiation_repository, _ = repositories
    scenario_id = uuid4()
    now = datetime.now(UTC)
    session = negotiation_repository.create(
        NegotiationSession(
            id=uuid4(),
            user_id=TEST_USER.id,
            scenario_id=scenario_id,
            status=NegotiationStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
    )

    response = client.post(f"/api/v1/negotiations/{session.id}/opponent-response")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": f"Scenario with id '{scenario_id}' was not found.",
        }
    }


def test_opponent_response_requires_existing_user_turn(
    client: TestClient,
) -> None:
    session = _create_session(client)
    expected_message = (
        "An opponent response cannot be generated for negotiation session "
        f"'{session['id']}' without a user turn."
    )

    response = client.post(f"/api/v1/negotiations/{session['id']}/opponent-response")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": expected_message,
        }
    }


def test_opponent_response_rejects_latest_opponent_turn(
    client: TestClient,
) -> None:
    session = _create_session(client)
    existing_turn = _create_turn(client, session["id"], speaker="opponent")
    expected_message = (
        "An opponent response cannot be generated for negotiation session "
        f"'{session['id']}' because the latest turn is from 'opponent'."
    )

    response = client.post(f"/api/v1/negotiations/{session['id']}/opponent-response")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": expected_message,
        }
    }
    history = client.get(f"/api/v1/negotiations/{session['id']}/turns").json()
    assert history == [existing_turn]


def test_empty_provider_response_returns_bad_gateway_without_persisting(
    client: TestClient,
    repositories: Repositories,
    coach_repository: CoachObservationRepository,
) -> None:
    session = _create_session(client)
    user_turn = _create_turn(client, session["id"])
    provider = MagicMock(spec=LLMProvider)
    provider.generate.return_value = "   "
    _replace_opponent_provider(repositories, coach_repository, provider)
    expected_message = (
        "The LLM provider returned an empty opponent response for negotiation "
        f"session '{session['id']}'."
    )

    response = client.post(f"/api/v1/negotiations/{session['id']}/opponent-response")

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": expected_message,
        }
    }
    history = client.get(f"/api/v1/negotiations/{session['id']}/turns").json()
    assert history == [user_turn]
    assert (
        coach_repository.list_by_session_for_user(
            _parse_uuid(session["id"]), TEST_USER.id
        )
        == []
    )


def test_provider_exception_propagates_without_persisting(
    client: TestClient,
    repositories: Repositories,
    coach_repository: CoachObservationRepository,
) -> None:
    session = _create_session(client)
    user_turn = _create_turn(client, session["id"])
    expected_error = RuntimeError("Provider failed")
    provider = MagicMock(spec=LLMProvider)
    provider.generate.side_effect = expected_error
    _replace_opponent_provider(repositories, coach_repository, provider)

    with pytest.raises(RuntimeError) as exc_info:
        client.post(f"/api/v1/negotiations/{session['id']}/opponent-response")

    assert exc_info.value is expected_error
    history = client.get(f"/api/v1/negotiations/{session['id']}/turns").json()
    assert history == [user_turn]
    assert (
        coach_repository.list_by_session_for_user(
            _parse_uuid(session["id"]), TEST_USER.id
        )
        == []
    )


def test_streamed_response_emits_chunks_and_persists_one_coached_turn(
    client: TestClient,
    coach_repository: CoachObservationRepository,
) -> None:
    session = _create_session(client)
    user_turn = _create_turn(client, session["id"])

    response = client.post(
        f"/api/v1/negotiations/{session['id']}/opponent-response/stream"
    )
    events = _stream_events(response.text)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert events[0] == {"type": "started"}
    assert len([event for event in events if event["type"] == "delta"]) > 1
    completed = events[-1]
    assert completed["type"] == "completed"
    turn = completed["turn"]
    assert isinstance(turn, dict)
    assert turn["content"] == FAKE_RESPONSE
    assert turn["speaker"] == "opponent"

    history = client.get(f"/api/v1/negotiations/{session['id']}/turns").json()
    assert history == [user_turn, turn]
    observations = coach_repository.list_by_session_for_user(
        _parse_uuid(session["id"]),
        TEST_USER.id,
    )
    assert len(observations) == 1
    assert observations[0].opponent_turn_id == _parse_uuid(turn["id"])


def test_stream_provider_failure_emits_safe_error_without_persistence_or_coach(
    client: TestClient,
    repositories: Repositories,
    coach_repository: CoachObservationRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = _create_session(client)
    user_turn = _create_turn(client, session["id"])
    sensitive_partial = "SENSITIVE STREAM CONTENT"
    provider = MagicMock(spec=LLMProvider)

    def failing_stream() -> Iterator[str]:
        yield sensitive_partial
        raise RuntimeError("private provider failure")

    provider.stream.return_value = failing_stream()
    _replace_opponent_provider(repositories, coach_repository, provider)

    with caplog.at_level(logging.DEBUG):
        response = client.post(
            f"/api/v1/negotiations/{session['id']}/opponent-response/stream"
        )
    events = _stream_events(response.text)

    assert response.status_code == 200
    assert events[-1] == {
        "type": "error",
        "code": "opponent_stream_failed",
        "message": "The opponent response could not be generated. Please try again.",
    }
    assert sensitive_partial not in caplog.text
    assert "private provider failure" not in caplog.text
    assert client.get(f"/api/v1/negotiations/{session['id']}/turns").json() == [
        user_turn
    ]
    assert (
        coach_repository.list_by_session_for_user(
            _parse_uuid(session["id"]),
            TEST_USER.id,
        )
        == []
    )


def test_empty_stream_output_emits_error_without_persisting(
    client: TestClient,
    repositories: Repositories,
    coach_repository: CoachObservationRepository,
) -> None:
    session = _create_session(client)
    user_turn = _create_turn(client, session["id"])
    provider = MagicMock(spec=LLMProvider)
    provider.stream.return_value = iter(["  "])
    _replace_opponent_provider(repositories, coach_repository, provider)

    response = client.post(
        f"/api/v1/negotiations/{session['id']}/opponent-response/stream"
    )

    assert _stream_events(response.text)[-1]["code"] == "empty_opponent_response"
    assert client.get(f"/api/v1/negotiations/{session['id']}/turns").json() == [
        user_turn
    ]
    assert (
        coach_repository.list_by_session_for_user(
            _parse_uuid(session["id"]),
            TEST_USER.id,
        )
        == []
    )


def test_failed_stream_can_be_retried_successfully(
    client: TestClient,
    repositories: Repositories,
    coach_repository: CoachObservationRepository,
) -> None:
    session = _create_session(client)
    user_turn = _create_turn(client, session["id"])
    provider = MagicMock(spec=LLMProvider)
    provider.stream.side_effect = [
        iter(()),
        iter([FAKE_RESPONSE]),
    ]
    _replace_opponent_provider(repositories, coach_repository, provider)

    failed = client.post(
        f"/api/v1/negotiations/{session['id']}/opponent-response/stream"
    )
    retried = client.post(
        f"/api/v1/negotiations/{session['id']}/opponent-response/stream"
    )

    assert _stream_events(failed.text)[-1]["type"] == "error"
    completed = _stream_events(retried.text)[-1]
    assert completed["type"] == "completed"
    assert provider.stream.call_count == 2
    assert len(client.get(f"/api/v1/negotiations/{session['id']}/turns").json()) == 2
    assert client.get(f"/api/v1/negotiations/{session['id']}/turns").json()[0] == (
        user_turn
    )


def test_stream_preserves_not_found_and_sequence_errors_before_headers(
    client: TestClient,
) -> None:
    missing = client.post(f"/api/v1/negotiations/{uuid4()}/opponent-response/stream")
    session = _create_session(client)
    no_turn = client.post(
        f"/api/v1/negotiations/{session['id']}/opponent-response/stream"
    )
    _create_turn(client, session["id"], speaker="opponent")
    out_of_sequence = client.post(
        f"/api/v1/negotiations/{session['id']}/opponent-response/stream"
    )

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert no_turn.status_code == 409
    assert out_of_sequence.status_code == 409
