from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class NegotiationStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class NegotiationSession:
    id: UUID
    scenario_id: UUID
    status: NegotiationStatus
    created_at: datetime
    updated_at: datetime
