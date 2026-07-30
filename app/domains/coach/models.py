from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CoachObservation:
    strengths: list[str]
    weaknesses: list[str]
    missed_opportunities: list[str]
    risk_signals: list[str]
    confidence: str


@dataclass(frozen=True)
class CoachObservationRecord:
    id: UUID
    session_id: UUID
    user_turn_id: UUID
    opponent_turn_id: UUID
    observation: CoachObservation
    created_at: datetime
