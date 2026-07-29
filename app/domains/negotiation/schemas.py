from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints

from app.domains.negotiation.models import (
    NegotiationDifficulty,
    NegotiationStatus,
)


class NegotiationSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=100),
    ]
    scenario: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=10, max_length=2000),
    ]
    difficulty: NegotiationDifficulty = NegotiationDifficulty.MEDIUM


class NegotiationSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    scenario: str
    difficulty: NegotiationDifficulty
    status: NegotiationStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime
