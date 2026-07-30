from datetime import UTC, datetime
from inspect import signature
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.services.coach import CoachService
from app.services.negotiation_engine import NegotiationEngine
from app.services.opponent import OpponentResponseResult, OpponentService


def _create_turn(
    session_id: UUID,
    turn_number: int,
    speaker: NegotiationTurnSpeaker,
    content: str,
) -> NegotiationTurn:
    return NegotiationTurn(
        id=uuid4(),
        session_id=session_id,
        speaker=speaker,
        content=content,
        turn_number=turn_number,
        created_at=datetime.now(UTC),
    )


def test_engine_delegates_to_opponent_service_and_returns_response() -> None:
    session_id = uuid4()
    user_turn = _create_turn(
        session_id,
        1,
        NegotiationTurnSpeaker.USER,
        "We need a ten percent reduction.",
    )
    opponent_turn = _create_turn(
        session_id,
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "We can consider a smaller adjustment.",
    )
    opponent_service = MagicMock(spec=OpponentService)
    opponent_service.generate_response.return_value = OpponentResponseResult(
        user_turn=user_turn,
        opponent_turn=opponent_turn,
        conversation_turns=[user_turn, opponent_turn],
    )
    coach_service = MagicMock(spec=CoachService)
    engine = NegotiationEngine(opponent_service, coach_service)

    result = engine.generate_response(session_id)

    assert result is opponent_turn
    opponent_service.generate_response.assert_called_once_with(session_id)


def test_engine_passes_completed_user_opponent_exchange_to_coach() -> None:
    session_id = uuid4()
    user_turn = _create_turn(
        session_id,
        1,
        NegotiationTurnSpeaker.USER,
        "We need a ten percent reduction.",
    )
    opponent_turn = _create_turn(
        session_id,
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "We can consider a smaller adjustment.",
    )
    conversation_turns = [user_turn, opponent_turn]
    opponent_service = MagicMock(spec=OpponentService)
    opponent_service.generate_response.return_value = OpponentResponseResult(
        user_turn=user_turn,
        opponent_turn=opponent_turn,
        conversation_turns=conversation_turns,
    )
    coach_service = MagicMock(spec=CoachService)
    engine = NegotiationEngine(opponent_service, coach_service)

    engine.generate_response(session_id)

    coach_service.analyze_exchange.assert_called_once_with(
        session_id,
        conversation_turns,
        user_turn,
        opponent_turn,
    )
    coached_turns = coach_service.analyze_exchange.call_args.args[1]
    assert coached_turns[0] is user_turn
    assert coached_turns[1] is opponent_turn
    assert [turn.turn_number for turn in coached_turns] == [1, 2]


def test_engine_includes_prior_conversation_turns_in_coach_context() -> None:
    session_id = uuid4()
    prior_user_turn = _create_turn(
        session_id,
        1,
        NegotiationTurnSpeaker.USER,
        "We can offer a two-year commitment.",
    )
    prior_opponent_turn = _create_turn(
        session_id,
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "We need a three-year commitment.",
    )
    latest_user_turn = _create_turn(
        session_id,
        3,
        NegotiationTurnSpeaker.USER,
        "Can a higher upfront payment bridge the difference?",
    )
    generated_opponent_turn = _create_turn(
        session_id,
        4,
        NegotiationTurnSpeaker.OPPONENT,
        "A larger upfront payment could support a shorter term.",
    )
    conversation_turns = [
        prior_user_turn,
        prior_opponent_turn,
        latest_user_turn,
        generated_opponent_turn,
    ]
    opponent_service = MagicMock(spec=OpponentService)
    opponent_service.generate_response.return_value = OpponentResponseResult(
        user_turn=latest_user_turn,
        opponent_turn=generated_opponent_turn,
        conversation_turns=conversation_turns,
    )
    coach_service = MagicMock(spec=CoachService)
    engine = NegotiationEngine(opponent_service, coach_service)

    engine.generate_response(session_id)

    coach_service.analyze_exchange.assert_called_once_with(
        session_id,
        conversation_turns,
        latest_user_turn,
        generated_opponent_turn,
    )


def test_engine_calls_opponent_before_coach() -> None:
    session_id = uuid4()
    user_turn = _create_turn(
        session_id,
        1,
        NegotiationTurnSpeaker.USER,
        "We need a ten percent reduction.",
    )
    opponent_turn = _create_turn(
        session_id,
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "We can consider a smaller adjustment.",
    )
    result = OpponentResponseResult(
        user_turn=user_turn,
        opponent_turn=opponent_turn,
        conversation_turns=[user_turn, opponent_turn],
    )
    call_order: list[str] = []
    opponent_service = MagicMock(spec=OpponentService)
    opponent_service.generate_response.side_effect = lambda _session_id: (
        call_order.append("opponent") or result
    )
    coach_service = MagicMock(spec=CoachService)
    coach_service.analyze_exchange.side_effect = lambda *_args: (
        call_order.append("coach") or None
    )
    engine = NegotiationEngine(opponent_service, coach_service)

    engine.generate_response(session_id)

    assert call_order == ["opponent", "coach"]


def test_opponent_service_has_no_coach_dependency() -> None:
    parameters = signature(OpponentService.__init__).parameters

    assert "coach_service" not in parameters


def test_coach_service_has_no_opponent_dependency() -> None:
    parameters = signature(CoachService.__init__).parameters

    assert "opponent_service" not in parameters


def test_negotiation_engine_has_no_repository_dependency() -> None:
    parameters = signature(NegotiationEngine.__init__).parameters

    assert not any("repository" in name for name in parameters)
