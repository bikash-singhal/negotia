from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.domains.scenario.models import ScenarioDifficulty


class ScenarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    industry: str
    opponent_role: str
    objective: str
    difficulty: ScenarioDifficulty
    constraints: list[str]
    personality: str
    negotiation_style: str
    hidden_context: list[str]
    walk_away_conditions: list[str]


class ScenarioGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    difficulty: ScenarioDifficulty
    description: str


class ScenarioGeneratedFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    industry: str
    opponent_role: str
    objective: str
    personality: str
    negotiation_style: str
    constraints: list[str]
    hidden_context: list[str]
    walk_away_conditions: list[str]


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: UUID
    title: str
    description: str
    industry: str
    opponent_role: str
    objective: str
    difficulty: ScenarioDifficulty
    constraints: list[str]
    personality: str
    negotiation_style: str
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ScenarioInternalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: UUID
    title: str
    description: str
    industry: str
    opponent_role: str
    objective: str
    difficulty: ScenarioDifficulty
    constraints: list[str]
    personality: str
    negotiation_style: str
    hidden_context: list[str]
    walk_away_conditions: list[str]
    created_at: AwareDatetime
    updated_at: AwareDatetime
