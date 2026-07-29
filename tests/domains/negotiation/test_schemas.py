from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.schemas import (
    NegotiationSessionCreate,
    NegotiationSessionResponse,
)


def _create_session() -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        scenario_id=uuid4(),
        status=NegotiationStatus.CREATED,
        created_at=now,
        updated_at=now,
    )


def test_session_create_accepts_valid_scenario_id() -> None:
    scenario_id = uuid4()

    request = NegotiationSessionCreate(scenario_id=scenario_id)

    assert request.scenario_id == scenario_id


def test_session_create_rejects_invalid_uuid() -> None:
    with pytest.raises(ValidationError):
        NegotiationSessionCreate(scenario_id="not-a-uuid")


def test_session_create_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        NegotiationSessionCreate(
            scenario_id=uuid4(),
            unexpected_field="unexpected value",
        )


def test_session_response_validates_from_domain_model() -> None:
    session = _create_session()

    response = NegotiationSessionResponse.model_validate(session)

    assert response.id == session.id
    assert response.scenario_id == session.scenario_id
    assert response.status is NegotiationStatus.CREATED


def test_session_response_timestamps_are_timezone_aware() -> None:
    response = NegotiationSessionResponse.model_validate(_create_session())

    assert response.created_at.tzinfo is not None
    assert response.updated_at.tzinfo is not None
