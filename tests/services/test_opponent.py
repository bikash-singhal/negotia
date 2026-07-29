from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.negotiation.exceptions import ScenarioNotFoundError
from app.domains.negotiation.models import (
    NegotiationSession,
    NegotiationStatus,
)
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation_turn.exceptions import (
    EmptyOpponentResponseError,
    NegotiationSessionNotFoundError,
    OpponentResponseOutOfSequenceError,
    OpponentResponseRequiresUserTurnError,
)
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.scenario.repository import ScenarioRepository
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider
from app.prompts.opponent import OpponentPromptBuilder
from app.services.opponent import OpponentService

FAKE_RESPONSE = (
    "I understand your position, but those terms are difficult for us to accept."
)


def _create_scenario(
    repository: ScenarioRepository,
) -> Scenario:
    return repository.create(
        Scenario(
            title="Enterprise software renewal",
            description="Negotiate the renewal of a multi-year software agreement.",
            industry="Technology",
            opponent_role="Vendor account executive",
            objective="Secure a three-year renewal at the current annual price.",
            difficulty=ScenarioDifficulty.ADVANCED,
            constraints=["Discount authority is limited to five percent."],
            personality="Confident and detail-oriented",
            negotiation_style="Competitive but pragmatic",
            hidden_context=["The vendor needs this deal to meet its quarterly target."],
            walk_away_conditions=[
                "No agreement below the current annual contract value."
            ],
        )
    )


def _create_session(
    repository: NegotiationRepository,
    scenario_id: UUID,
) -> NegotiationSession:
    now = datetime.now(UTC)
    return repository.create(
        NegotiationSession(
            id=uuid4(),
            scenario_id=scenario_id,
            status=NegotiationStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
    )


def _create_turn(
    repository: NegotiationTurnRepository,
    session_id: UUID,
    *,
    speaker: NegotiationTurnSpeaker = NegotiationTurnSpeaker.USER,
    turn_number: int = 1,
    content: str = "We need a ten percent reduction.",
) -> NegotiationTurn:
    return repository.create(
        NegotiationTurn(
            id=uuid4(),
            session_id=session_id,
            speaker=speaker,
            content=content,
            turn_number=turn_number,
            created_at=datetime.now(UTC),
        )
    )


def test_generate_response_creates_and_persists_opponent_turn() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    turn_repository = NegotiationTurnRepository()
    scenario = _create_scenario(scenario_repository)
    session = _create_session(negotiation_repository, scenario.scenario_id)
    user_turn = _create_turn(turn_repository, session.id)
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        OpponentPromptBuilder(),
        FakeLLMProvider(),
    )

    turn = service.generate_response(session.id)

    assert isinstance(turn, NegotiationTurn)
    assert isinstance(turn.id, UUID)
    assert turn.speaker is NegotiationTurnSpeaker.OPPONENT
    assert turn.session_id == session.id
    assert turn.content == FAKE_RESPONSE
    assert turn.turn_number == user_turn.turn_number + 1
    assert turn.created_at.tzinfo is not None
    assert turn.created_at.utcoffset() == timedelta(0)
    assert turn_repository.get(turn.id) is turn


def test_generate_response_builds_prompts_and_strips_content() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    turn_repository = NegotiationTurnRepository()
    scenario = _create_scenario(scenario_repository)
    session = _create_session(negotiation_repository, scenario.scenario_id)
    turns = [
        _create_turn(turn_repository, session.id),
        _create_turn(
            turn_repository,
            session.id,
            speaker=NegotiationTurnSpeaker.OPPONENT,
            turn_number=2,
            content="We can consider a smaller adjustment.",
        ),
        _create_turn(
            turn_repository,
            session.id,
            turn_number=3,
            content="Could you meet us halfway?",
        ),
    ]
    prompt_builder = MagicMock(spec=OpponentPromptBuilder)
    prompt_builder.build_system_prompt.return_value = "system prompt"
    prompt_builder.build_user_prompt.return_value = "user prompt"
    llm_provider = MagicMock(spec=LLMProvider)
    llm_provider.generate.return_value = "  Generated opponent response.  "
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        prompt_builder,
        llm_provider,
    )

    turn = service.generate_response(session.id)

    assert turn.content == "Generated opponent response."
    assert turn.turn_number == 4
    prompt_builder.build_system_prompt.assert_called_once_with(scenario)
    prompt_builder.build_user_prompt.assert_called_once_with(turns)
    llm_provider.generate.assert_called_once_with(
        system_prompt="system prompt",
        user_prompt="user prompt",
    )


def test_missing_session_stops_before_other_dependencies() -> None:
    session_id = uuid4()
    negotiation_repository = MagicMock(spec=NegotiationRepository)
    negotiation_repository.get.return_value = None
    scenario_repository = MagicMock(spec=ScenarioRepository)
    turn_repository = MagicMock(spec=NegotiationTurnRepository)
    prompt_builder = MagicMock(spec=OpponentPromptBuilder)
    llm_provider = MagicMock(spec=LLMProvider)
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        prompt_builder,
        llm_provider,
    )

    with pytest.raises(NegotiationSessionNotFoundError) as exc_info:
        service.generate_response(session_id)

    assert exc_info.value.session_id == session_id
    scenario_repository.get.assert_not_called()
    turn_repository.list_by_session.assert_not_called()
    turn_repository.create.assert_not_called()
    prompt_builder.build_system_prompt.assert_not_called()
    prompt_builder.build_user_prompt.assert_not_called()
    llm_provider.generate.assert_not_called()


def test_missing_scenario_stops_before_turns_and_provider() -> None:
    scenario_id = uuid4()
    session = NegotiationSession(
        id=uuid4(),
        scenario_id=scenario_id,
        status=NegotiationStatus.CREATED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    negotiation_repository = MagicMock(spec=NegotiationRepository)
    negotiation_repository.get.return_value = session
    scenario_repository = MagicMock(spec=ScenarioRepository)
    scenario_repository.get.return_value = None
    turn_repository = MagicMock(spec=NegotiationTurnRepository)
    prompt_builder = MagicMock(spec=OpponentPromptBuilder)
    llm_provider = MagicMock(spec=LLMProvider)
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        prompt_builder,
        llm_provider,
    )

    with pytest.raises(ScenarioNotFoundError) as exc_info:
        service.generate_response(session.id)

    assert exc_info.value.scenario_id == scenario_id
    turn_repository.list_by_session.assert_not_called()
    turn_repository.create.assert_not_called()
    prompt_builder.build_system_prompt.assert_not_called()
    llm_provider.generate.assert_not_called()


def test_empty_history_does_not_call_provider() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    scenario = _create_scenario(scenario_repository)
    session = _create_session(negotiation_repository, scenario.scenario_id)
    turn_repository = MagicMock(spec=NegotiationTurnRepository)
    turn_repository.list_by_session.return_value = []
    llm_provider = MagicMock(spec=LLMProvider)
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        MagicMock(spec=OpponentPromptBuilder),
        llm_provider,
    )

    with pytest.raises(OpponentResponseRequiresUserTurnError):
        service.generate_response(session.id)

    llm_provider.generate.assert_not_called()
    turn_repository.create.assert_not_called()


def test_latest_opponent_turn_does_not_call_provider() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    scenario = _create_scenario(scenario_repository)
    session = _create_session(negotiation_repository, scenario.scenario_id)
    turn_repository = MagicMock(spec=NegotiationTurnRepository)
    latest_turn = NegotiationTurn(
        id=uuid4(),
        session_id=session.id,
        speaker=NegotiationTurnSpeaker.OPPONENT,
        content="We can consider a smaller adjustment.",
        turn_number=2,
        created_at=datetime.now(UTC),
    )
    turn_repository.list_by_session.return_value = [latest_turn]
    llm_provider = MagicMock(spec=LLMProvider)
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        MagicMock(spec=OpponentPromptBuilder),
        llm_provider,
    )

    with pytest.raises(OpponentResponseOutOfSequenceError) as exc_info:
        service.generate_response(session.id)

    assert exc_info.value.latest_speaker is NegotiationTurnSpeaker.OPPONENT
    llm_provider.generate.assert_not_called()
    turn_repository.create.assert_not_called()


@pytest.mark.parametrize(
    "generated_content",
    ["", "   "],
    ids=["blank", "whitespace-only"],
)
def test_empty_generated_content_is_not_persisted(
    generated_content: str,
) -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    turn_repository = NegotiationTurnRepository()
    scenario = _create_scenario(scenario_repository)
    session = _create_session(negotiation_repository, scenario.scenario_id)
    user_turn = _create_turn(turn_repository, session.id)
    llm_provider = MagicMock(spec=LLMProvider)
    llm_provider.generate.return_value = generated_content
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        OpponentPromptBuilder(),
        llm_provider,
    )

    with pytest.raises(EmptyOpponentResponseError):
        service.generate_response(session.id)

    assert turn_repository.list_by_session(session.id) == [user_turn]


def test_provider_exception_propagates_without_persisting_turn() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    turn_repository = NegotiationTurnRepository()
    scenario = _create_scenario(scenario_repository)
    session = _create_session(negotiation_repository, scenario.scenario_id)
    user_turn = _create_turn(turn_repository, session.id)
    expected_error = RuntimeError("Provider failed")
    llm_provider = MagicMock(spec=LLMProvider)
    llm_provider.generate.side_effect = expected_error
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        OpponentPromptBuilder(),
        llm_provider,
    )

    with pytest.raises(RuntimeError) as exc_info:
        service.generate_response(session.id)

    assert exc_info.value is expected_error
    assert turn_repository.list_by_session(session.id) == [user_turn]


def test_generation_uses_only_requested_session_history() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    turn_repository = NegotiationTurnRepository()
    scenario = _create_scenario(scenario_repository)
    requested_session = _create_session(
        negotiation_repository,
        scenario.scenario_id,
    )
    other_session = _create_session(
        negotiation_repository,
        scenario.scenario_id,
    )
    requested_turn = _create_turn(
        turn_repository,
        requested_session.id,
        turn_number=1,
    )
    other_turn = _create_turn(
        turn_repository,
        other_session.id,
        turn_number=7,
    )
    prompt_builder = MagicMock(spec=OpponentPromptBuilder)
    prompt_builder.build_system_prompt.return_value = "system prompt"
    prompt_builder.build_user_prompt.return_value = "user prompt"
    llm_provider = MagicMock(spec=LLMProvider)
    llm_provider.generate.return_value = "Generated response."
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        prompt_builder,
        llm_provider,
    )

    generated_turn = service.generate_response(requested_session.id)

    assert generated_turn.session_id == requested_session.id
    assert generated_turn.turn_number == 2
    prompt_builder.build_user_prompt.assert_called_once_with([requested_turn])
    assert turn_repository.list_by_session(other_session.id) == [other_turn]
