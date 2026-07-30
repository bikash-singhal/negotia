from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class NegotiationDebrief:
    repeated_strengths: list[str]
    repeated_weaknesses: list[str]
    key_missed_opportunities: list[str]
    recurring_risks: list[str]
    overall_assessment: str
    confidence: str


@dataclass(frozen=True)
class NegotiationDebriefRecord:
    id: UUID
    session_id: UUID
    debrief: NegotiationDebrief
    observation_count: int
    created_at: datetime
