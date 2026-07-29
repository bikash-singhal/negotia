from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints

from app.domains.negotiation_turn.models import NegotiationTurnSpeaker


class NegotiationTurnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    speaker: NegotiationTurnSpeaker
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class NegotiationTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    speaker: NegotiationTurnSpeaker
    content: str
    turn_number: int
    created_at: AwareDatetime
