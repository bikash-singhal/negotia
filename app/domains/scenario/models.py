from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ScenarioDifficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Scenario:
    title: str
    description: str
    industry: str
    opponent_role: str
    objective: str
    difficulty: ScenarioDifficulty
    personality: str
    negotiation_style: str
    user_id: UUID
    scenario_id: UUID = field(default_factory=uuid4)
    constraints: list[str] = field(default_factory=list)
    hidden_context: list[str] = field(default_factory=list)
    walk_away_conditions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
