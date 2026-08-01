from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveInt


class NegotiatorMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    recurring_strengths: list[str]
    recurring_weaknesses: list[str]
    improving_skills: list[str]
    persistent_risks: list[str]
    priority_focus_areas: list[str]
    recommended_drills: list[str]
    sessions_analyzed: PositiveInt
    confidence: str


@dataclass(frozen=True)
class NegotiatorMemoryRecord:
    id: UUID
    user_id: UUID
    trigger_session_id: UUID | None
    memory: NegotiatorMemory
    source_session_ids: tuple[UUID, ...]
    created_at: datetime
