from datetime import UTC, datetime
from inspect import signature
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.debrief.exceptions import NoCoachObservationsError
from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.domains.negotiation.exceptions import (
    CompletedNegotiationMissingDebriefError,
    NegotiationCompletionLatestTurnFromUserError,
    NegotiationCompletionRequiresExchangeError,
    NegotiationCompletionWithoutTurnsError,
)
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.services.coach import CoachService
from app.services.debrief import DebriefService
from app.services.negotiation_engine import (
    NegotiationCompletionResult,
    NegotiationEngine,
)
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


def _build_engine(
    opponent_service: OpponentService,
    coach_service: CoachService,
) -> NegotiationEngine:
    return NegotiationEngine(
        opponent_service,
        coach_service,
        MagicMock(spec=NegotiationService),
        MagicMock(spec=NegotiationTurnService),
        MagicMock(spec=DebriefService),
    )


def _create_session(
    status: NegotiationStatus = NegotiationStatus.CREATED,
) -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        scenario_id=uuid4(),
        status=status,
        created_at=now,
        updated_at=now,
    )


def _create_debrief_record(session_id: UUID) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=NegotiationDebrief(
            repeated_strengths=["Uses conditional trades."],
            repeated_weaknesses=[],
            key_missed_opportunities=[],
            recurring_risks=[],
            overall_assessment="The user negotiated constructively.",
            confidence="high",
        ),
        observation_count=1,
        created_at=datetime.now(UTC),
    )


def _build_completion_engine(
    session: NegotiationSession,
    turns: list[NegotiationTurn],
) -> tuple[
    NegotiationEngine,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    negotiation_service = MagicMock(spec=NegotiationService)
    negotiation_service.validate_completion_transition.return_value = session
    negotiation_service.mark_completed.side_effect = lambda _session_id: session
    turn_service = MagicMock(spec=NegotiationTurnService)
    turn_service.list_turns.return_value = turns
    debrief_service = MagicMock(spec=DebriefService)
    engine = NegotiationEngine(
        MagicMock(spec=OpponentService),
        MagicMock(spec=CoachService),
        negotiation_service,
        turn_service,
        debrief_service,
    )
    return engine, negotiation_service, turn_service, debrief_service


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
    engine = _build_engine(opponent_service, coach_service)

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
    engine = _build_engine(opponent_service, coach_service)

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
    engine = _build_engine(opponent_service, coach_service)

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
    engine = _build_engine(opponent_service, coach_service)

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


def test_completion_validates_turns_then_generates_debrief_then_marks_completed() -> (
    None
):
    session = _create_session()
    user_turn = _create_turn(
        session.id,
        1,
        NegotiationTurnSpeaker.USER,
        "We can commit for two years.",
    )
    opponent_turn = _create_turn(
        session.id,
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "That could support a discount.",
    )
    engine, negotiation_service, turn_service, debrief_service = (
        _build_completion_engine(session, [user_turn, opponent_turn])
    )
    record = _create_debrief_record(session.id)
    call_order: list[str] = []
    negotiation_service.validate_completion_transition.side_effect = (
        lambda received_id: call_order.append("session") or session
    )
    turn_service.list_turns.side_effect = lambda received_id: (
        call_order.append("turns") or [user_turn, opponent_turn]
    )
    debrief_service.get_for_session.side_effect = lambda received_id: (
        call_order.append("debrief lookup") or None
    )
    debrief_service.generate_for_session.side_effect = lambda received_id: (
        call_order.append("debrief generation") or record
    )

    def mark_completed(received_id: UUID) -> NegotiationSession:
        call_order.append("completion")
        session.status = NegotiationStatus.COMPLETED
        return session

    negotiation_service.mark_completed.side_effect = mark_completed

    result = engine.complete_session(session.id)

    assert isinstance(result, NegotiationCompletionResult)
    assert result.session is session
    assert result.debrief_record is record
    assert call_order == [
        "session",
        "turns",
        "debrief lookup",
        "debrief generation",
        "completion",
    ]
    negotiation_service.validate_completion_transition.assert_called_once_with(
        session.id
    )
    turn_service.list_turns.assert_called_once_with(session.id)
    debrief_service.get_for_session.assert_called_once_with(session.id)
    debrief_service.generate_for_session.assert_called_once_with(session.id)
    negotiation_service.mark_completed.assert_called_once_with(session.id)


def test_completion_rejects_session_without_turns_before_debrief() -> None:
    session = _create_session()
    engine, negotiation_service, _, debrief_service = _build_completion_engine(
        session,
        [],
    )

    with pytest.raises(NegotiationCompletionWithoutTurnsError):
        engine.complete_session(session.id)

    debrief_service.get_for_session.assert_not_called()
    debrief_service.generate_for_session.assert_not_called()
    negotiation_service.mark_completed.assert_not_called()


def test_completion_rejects_latest_user_turn_before_debrief() -> None:
    session = _create_session()
    user_turn = _create_turn(
        session.id,
        1,
        NegotiationTurnSpeaker.USER,
        "We need a lower price.",
    )
    engine, negotiation_service, _, debrief_service = _build_completion_engine(
        session,
        [user_turn],
    )

    with pytest.raises(NegotiationCompletionLatestTurnFromUserError):
        engine.complete_session(session.id)

    debrief_service.get_for_session.assert_not_called()
    debrief_service.generate_for_session.assert_not_called()
    negotiation_service.mark_completed.assert_not_called()


def test_completion_requires_adjacent_user_opponent_exchange() -> None:
    session = _create_session()
    first_opponent_turn = _create_turn(
        session.id,
        1,
        NegotiationTurnSpeaker.OPPONENT,
        "Here is our opening position.",
    )
    second_opponent_turn = _create_turn(
        session.id,
        2,
        NegotiationTurnSpeaker.OPPONENT,
        "Our position is unchanged.",
    )
    engine, negotiation_service, _, debrief_service = _build_completion_engine(
        session,
        [first_opponent_turn, second_opponent_turn],
    )

    with pytest.raises(NegotiationCompletionRequiresExchangeError):
        engine.complete_session(session.id)

    debrief_service.generate_for_session.assert_not_called()
    negotiation_service.mark_completed.assert_not_called()


def test_completion_does_not_mark_session_when_debrief_generation_fails() -> None:
    session = _create_session()
    turns = [
        _create_turn(
            session.id,
            1,
            NegotiationTurnSpeaker.USER,
            "We need a lower price.",
        ),
        _create_turn(
            session.id,
            2,
            NegotiationTurnSpeaker.OPPONENT,
            "We can discuss a smaller adjustment.",
        ),
    ]
    engine, negotiation_service, _, debrief_service = _build_completion_engine(
        session,
        turns,
    )
    expected_error = NoCoachObservationsError()
    debrief_service.get_for_session.return_value = None
    debrief_service.generate_for_session.side_effect = expected_error

    with pytest.raises(NoCoachObservationsError) as exc_info:
        engine.complete_session(session.id)

    assert exc_info.value is expected_error
    negotiation_service.mark_completed.assert_not_called()


def test_completion_reuses_existing_debrief_for_recovery() -> None:
    session = _create_session()
    turns = [
        _create_turn(
            session.id,
            1,
            NegotiationTurnSpeaker.USER,
            "We need a lower price.",
        ),
        _create_turn(
            session.id,
            2,
            NegotiationTurnSpeaker.OPPONENT,
            "We can discuss a smaller adjustment.",
        ),
    ]
    engine, negotiation_service, _, debrief_service = _build_completion_engine(
        session,
        turns,
    )
    record = _create_debrief_record(session.id)
    debrief_service.get_for_session.return_value = record
    negotiation_service.mark_completed.side_effect = lambda _session_id: (
        setattr(session, "status", NegotiationStatus.COMPLETED) or session
    )

    result = engine.complete_session(session.id)

    assert result.debrief_record is record
    assert result.session.status is NegotiationStatus.COMPLETED
    debrief_service.generate_for_session.assert_not_called()
    negotiation_service.mark_completed.assert_called_once_with(session.id)


def test_completed_session_returns_original_result_without_revalidation() -> None:
    session = _create_session(NegotiationStatus.COMPLETED)
    original_updated_at = session.updated_at
    engine, negotiation_service, turn_service, debrief_service = (
        _build_completion_engine(session, [])
    )
    record = _create_debrief_record(session.id)
    debrief_service.get_for_session.return_value = record

    first = engine.complete_session(session.id)
    second = engine.complete_session(session.id)

    assert first.session is second.session is session
    assert first.debrief_record is second.debrief_record is record
    assert session.updated_at is original_updated_at
    assert debrief_service.get_for_session.call_count == 2
    turn_service.list_turns.assert_not_called()
    debrief_service.generate_for_session.assert_not_called()
    negotiation_service.mark_completed.assert_not_called()


def test_completed_session_without_debrief_raises_consistency_error() -> None:
    session = _create_session(NegotiationStatus.COMPLETED)
    engine, negotiation_service, turn_service, debrief_service = (
        _build_completion_engine(session, [])
    )
    debrief_service.get_for_session.return_value = None

    with pytest.raises(CompletedNegotiationMissingDebriefError) as exc_info:
        engine.complete_session(session.id)

    assert exc_info.value.session_id == session.id
    turn_service.list_turns.assert_not_called()
    debrief_service.generate_for_session.assert_not_called()
    negotiation_service.mark_completed.assert_not_called()
