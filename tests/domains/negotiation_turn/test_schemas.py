from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.schemas import (
    NegotiationTurnCreate,
    NegotiationTurnResponse,
)


def _valid_turn_data() -> dict[str, object]:
    return {
        "session_id": str(uuid4()),
        "speaker": "user",
        "content": "I would like to discuss the contract terms.",
    }


def test_turn_create_accepts_user_speaker() -> None:
    request = NegotiationTurnCreate.model_validate(_valid_turn_data())

    assert request.speaker is NegotiationTurnSpeaker.USER


def test_turn_create_accepts_opponent_speaker() -> None:
    data = _valid_turn_data()
    data["speaker"] = "opponent"

    request = NegotiationTurnCreate.model_validate(data)

    assert request.speaker is NegotiationTurnSpeaker.OPPONENT


def test_turn_create_rejects_unsupported_speaker() -> None:
    data = _valid_turn_data()
    data["speaker"] = "coach"

    with pytest.raises(ValidationError):
        NegotiationTurnCreate.model_validate(data)


def test_turn_create_rejects_empty_content() -> None:
    data = _valid_turn_data()
    data["content"] = ""

    with pytest.raises(ValidationError):
        NegotiationTurnCreate.model_validate(data)


def test_turn_create_rejects_whitespace_only_content() -> None:
    data = _valid_turn_data()
    data["content"] = "   "

    with pytest.raises(ValidationError):
        NegotiationTurnCreate.model_validate(data)


def test_turn_create_rejects_server_managed_fields() -> None:
    data = _valid_turn_data()
    data["id"] = str(uuid4())

    with pytest.raises(ValidationError):
        NegotiationTurnCreate.model_validate(data)


def test_turn_response_validates_from_domain_model() -> None:
    turn = NegotiationTurn(
        id=uuid4(),
        session_id=uuid4(),
        speaker=NegotiationTurnSpeaker.USER,
        content="I would like to discuss the contract terms.",
        turn_number=1,
        created_at=datetime.now(UTC),
    )

    response = NegotiationTurnResponse.model_validate(turn)

    assert response.id == turn.id
    assert response.session_id == turn.session_id
    assert response.speaker is NegotiationTurnSpeaker.USER
    assert response.content == turn.content
    assert response.turn_number == turn.turn_number
    assert response.created_at == turn.created_at
