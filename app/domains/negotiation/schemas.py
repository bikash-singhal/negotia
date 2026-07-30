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


class NegotiationDebriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    repeated_strengths: list[str]
    repeated_weaknesses: list[str]
    key_missed_opportunities: list[str]
    recurring_risks: list[str]
    overall_assessment: str
    confidence: str


class NegotiationTacticResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    priority: int
    title: str
    rationale: str
    actions: list[str]
    example_language: list[str]
    success_indicator: str


class NegotiationStrategyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    primary_objective: str
    expected_outcome: str
    prioritized_tactics: list[NegotiationTacticResponse]
    long_term_skills: list[str]
    preparation_checklist: list[str]
    avoid_next_time: list[str]
    confidence: str


class NegotiationCompletionResponse(BaseModel):
    session_id: UUID
    status: NegotiationStatus
    completed_at: AwareDatetime
    debrief: NegotiationDebriefResponse
    observation_count: int
    debrief_id: UUID
    debrief_created_at: AwareDatetime
    strategy: NegotiationStrategyResponse
    strategy_id: UUID
    strategy_created_at: AwareDatetime
