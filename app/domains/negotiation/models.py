from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class NegotiationDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class NegotiationStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass(frozen=True)
class NegotiationSession:
    id: UUID
    title: str
    scenario: str
    difficulty: NegotiationDifficulty
    status: NegotiationStatus
    created_at: datetime
    updated_at: datetime
