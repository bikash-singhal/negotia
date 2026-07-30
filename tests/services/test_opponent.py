from datetime import UTC, datetime, timedelta
from inspect import signature
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.adaptive_context.models import AdaptiveContext
from app.domains.negotiation.exceptions import ScenarioNotFoundError
from app.domains.negotiation.models import (
    NegotiationSession,
    NegotiationStatus,
)
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation_state.exceptions import InvalidNegotiationStateJsonError
from app.domains.negotiation_state.models import NegotiationState
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
from app.domains.opponent.profile_builder import OpponentProfileBuilder
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.scenario.repository import ScenarioRepository
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider
from app.prompts.opponent import OpponentPromptBuilder
from app.services.adaptive_context import AdaptiveContextService
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentResponseResult, OpponentService

FAKE_RESPONSE = (
    "I understand your position, but those terms are difficult for us to accept."
)


def _create_state() -> NegotiationState:
    return NegotiationState(
        latest_user_position="The user requested a ten percent reduction.",
        latest_opponent_position=None,
        agreements=[],
        open_topics=["Annual price"],
        unresolved_items=["Discount percentage"],
        negotiation_stage="bargaining",
    )


def _create_state_extractor() -> MagicMock:
    extractor = MagicMock(spec=NegotiationStateExtractor)
    extractor.extract.return_value = _create_state()
    return extractor


def _create_adaptive_context_service(
    context: AdaptiveContext | None = None,
) -> MagicMock:
    service = MagicMock(spec=AdaptiveContextService)
    service.get_context.return_value = context
    return service


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
    adaptive_context_service = _create_adaptive_context_service()
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        _create_state_extractor(),
        OpponentProfileBuilder(),
        OpponentPromptBuilder(),
        FakeLLMProvider(),
        adaptive_context_service,
    )

    result = service.generate_response(session.id)
    turn = result.opponent_turn

    assert isinstance(result, OpponentResponseResult)
    assert isinstance(turn, NegotiationTurn)
    assert isinstance(turn.id, UUID)
    assert turn.speaker is NegotiationTurnSpeaker.OPPONENT
    assert turn.session_id == session.id
    assert turn.content == FAKE_RESPONSE
    assert turn.turn_number == user_turn.turn_number + 1
    assert turn.created_at.tzinfo is not None
    assert turn.created_at.utcoffset() == timedelta(0)
    assert turn_repository.get(turn.id) is turn
    assert result.user_turn is user_turn
    assert result.conversation_turns == [user_turn, turn]
    adaptive_context_service.get_context.assert_called_once_with()


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
    expected_profile = OpponentProfileBuilder().build(scenario.difficulty)
    profile_builder = MagicMock(spec=OpponentProfileBuilder)
    profile_builder.build.return_value = expected_profile
    expected_state = _create_state()
    call_order: list[str] = []
    state_extractor = _create_state_extractor()
    state_extractor.extract.side_effect = lambda _turns: (
        call_order.append("extract") or expected_state
    )
    prompt_builder.build_system_prompt.side_effect = lambda *_args: (
        call_order.append("build_system") or "system prompt"
    )
    llm_provider = MagicMock(spec=LLMProvider)
    llm_provider.generate.side_effect = lambda **_kwargs: (
        call_order.append("generate") or "  Generated opponent response.  "
    )
    adaptive_context = AdaptiveContext(
        focus_areas=["Ask diagnostic questions"],
        coaching_focus=["Concession planning"],
        opponent_adjustments=["Test unilateral concessions"],
        strengths=["Uses objective criteria"],
    )
    adaptive_context_service = _create_adaptive_context_service(adaptive_context)
    adaptive_context_service.get_context.side_effect = lambda: (
        call_order.append("context") or adaptive_context
    )
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        state_extractor,
        profile_builder,
        prompt_builder,
        llm_provider,
        adaptive_context_service,
    )

    result = service.generate_response(session.id)
    turn = result.opponent_turn

    assert turn.content == "Generated opponent response."
    assert turn.turn_number == 4
    assert call_order == ["extract", "context", "build_system", "generate"]
    state_extractor.extract.assert_called_once_with(turns)
    profile_builder.build.assert_called_once_with(scenario.difficulty)
    prompt_builder.build_system_prompt.assert_called_once_with(
        scenario,
        expected_profile,
        expected_state,
        adaptive_context,
    )
    prompt_builder.build_user_prompt.assert_called_once_with(turns)
    llm_provider.generate.assert_called_once_with(
        system_prompt="system prompt",
        user_prompt="user prompt",
    )
    adaptive_context_service.get_context.assert_called_once_with()
    assert result.user_turn is turns[-1]
    assert result.conversation_turns == [*turns, turn]
    assert [item.turn_number for item in result.conversation_turns] == [1, 2, 3, 4]


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
        _create_state_extractor(),
        OpponentProfileBuilder(),
        prompt_builder,
        llm_provider,
        _create_adaptive_context_service(),
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
        _create_state_extractor(),
        OpponentProfileBuilder(),
        prompt_builder,
        llm_provider,
        _create_adaptive_context_service(),
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
        _create_state_extractor(),
        OpponentProfileBuilder(),
        MagicMock(spec=OpponentPromptBuilder),
        llm_provider,
        _create_adaptive_context_service(),
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
        _create_state_extractor(),
        OpponentProfileBuilder(),
        MagicMock(spec=OpponentPromptBuilder),
        llm_provider,
        _create_adaptive_context_service(),
    )

    with pytest.raises(OpponentResponseOutOfSequenceError) as exc_info:
        service.generate_response(session.id)

    assert exc_info.value.latest_speaker is NegotiationTurnSpeaker.OPPONENT
    llm_provider.generate.assert_not_called()
    turn_repository.create.assert_not_called()


def test_state_extraction_failure_does_not_persist_opponent_turn() -> None:
    negotiation_repository = NegotiationRepository()
    scenario_repository = ScenarioRepository()
    turn_repository = NegotiationTurnRepository()
    scenario = _create_scenario(scenario_repository)
    session = _create_session(negotiation_repository, scenario.scenario_id)
    user_turn = _create_turn(turn_repository, session.id)
    expected_error = InvalidNegotiationStateJsonError()
    state_extractor = _create_state_extractor()
    state_extractor.extract.side_effect = expected_error
    profile_builder = MagicMock(spec=OpponentProfileBuilder)
    prompt_builder = MagicMock(spec=OpponentPromptBuilder)
    llm_provider = MagicMock(spec=LLMProvider)
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        state_extractor,
        profile_builder,
        prompt_builder,
        llm_provider,
        _create_adaptive_context_service(),
    )

    with pytest.raises(InvalidNegotiationStateJsonError) as exc_info:
        service.generate_response(session.id)

    assert exc_info.value is expected_error
    assert turn_repository.list_by_session(session.id) == [user_turn]
    profile_builder.build.assert_not_called()
    prompt_builder.build_system_prompt.assert_not_called()
    prompt_builder.build_user_prompt.assert_not_called()
    llm_provider.generate.assert_not_called()


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
        _create_state_extractor(),
        OpponentProfileBuilder(),
        OpponentPromptBuilder(),
        llm_provider,
        _create_adaptive_context_service(),
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
        _create_state_extractor(),
        OpponentProfileBuilder(),
        OpponentPromptBuilder(),
        llm_provider,
        _create_adaptive_context_service(),
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
    state_extractor = _create_state_extractor()
    adaptive_context_service = _create_adaptive_context_service()
    service = OpponentService(
        negotiation_repository,
        scenario_repository,
        turn_repository,
        state_extractor,
        OpponentProfileBuilder(),
        prompt_builder,
        llm_provider,
        adaptive_context_service,
    )

    result = service.generate_response(requested_session.id)
    generated_turn = result.opponent_turn

    assert generated_turn.session_id == requested_session.id
    assert generated_turn.turn_number == 2
    assert result.user_turn is requested_turn
    assert result.conversation_turns == [requested_turn, generated_turn]
    state_extractor.extract.assert_called_once_with([requested_turn])
    adaptive_context_service.get_context.assert_called_once_with()
    prompt_builder.build_system_prompt.assert_called_once_with(
        scenario,
        OpponentProfileBuilder().build(scenario.difficulty),
        _create_state(),
        None,
    )
    prompt_builder.build_user_prompt.assert_called_once_with([requested_turn])
    llm_provider.generate.assert_called_once_with(
        system_prompt="system prompt",
        user_prompt="user prompt",
    )
    assert turn_repository.list_by_session(other_session.id) == [other_turn]


def test_opponent_service_has_only_adaptive_context_memory_boundary() -> None:
    parameters = signature(OpponentService.__init__).parameters

    assert "adaptive_context_service" in parameters
    assert "memory_service" not in parameters
    assert "memory_repository" not in parameters
