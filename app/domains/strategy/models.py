from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class NegotiationTactic:
    priority: int
    title: str
    rationale: str
    actions: list[str]
    example_language: list[str]
    success_indicator: str


@dataclass(frozen=True)
class NegotiationStrategy:
    primary_objective: str
    expected_outcome: str
    prioritized_tactics: list[NegotiationTactic]
    long_term_skills: list[str]
    preparation_checklist: list[str]
    avoid_next_time: list[str]
    confidence: str


@dataclass(frozen=True)
class NegotiationStrategyRecord:
    id: UUID
    session_id: UUID
    debrief_id: UUID
    strategy: NegotiationStrategy
    created_at: datetime
