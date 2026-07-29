from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.domains.negotiation.models import NegotiationStatus


class NegotiationSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: UUID


class NegotiationSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scenario_id: UUID
    status: NegotiationStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime
