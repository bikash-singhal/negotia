from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints

MemoryText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]


class NegotiatorMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    stable_strengths: list[MemoryText] = Field(max_length=3)
    stable_weaknesses: list[MemoryText] = Field(max_length=3)
    improving_skills: list[MemoryText] = Field(max_length=2)
    persistent_risks: list[MemoryText] = Field(max_length=2)
    highest_priority_skill: MemoryText
    next_session_drill: MemoryText
    progress_summary: MemoryText
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
