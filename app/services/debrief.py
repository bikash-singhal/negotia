import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, ValidationError

from app.domains.coach.models import CoachObservationRecord
from app.domains.coach.repository import CoachObservationRepository
from app.domains.debrief.exceptions import (
    EmptyDebriefResponseError,
    InvalidDebriefDataError,
    InvalidDebriefJsonError,
    NoCoachObservationsError,
)
from app.domains.debrief.models import (
    NegotiationDebrief,
    NegotiationDebriefRecord,
)
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.llm.provider import LLMProvider
from app.prompts.debrief import DebriefPromptBuilder


class _NegotiationDebriefPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repeated_strengths: list[str]
    repeated_weaknesses: list[str]
    key_missed_opportunities: list[str]
    recurring_risks: list[str]
    overall_assessment: str
    confidence: str


class DebriefExtractor:
    def __init__(
        self,
        prompt_builder: DebriefPromptBuilder,
        llm_provider: LLMProvider,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider

    def extract(
        self,
        observations: list[CoachObservationRecord],
    ) -> NegotiationDebrief:
        if not observations:
            raise NoCoachObservationsError()

        response = self._llm_provider.generate(
            system_prompt=self._prompt_builder.build_system_prompt(),
            user_prompt=self._prompt_builder.build_user_prompt(observations),
        ).strip()
        if not response:
            raise EmptyDebriefResponseError()

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            raise InvalidDebriefJsonError() from None

        try:
            payload = _NegotiationDebriefPayload.model_validate(data)
        except ValidationError:
            raise InvalidDebriefDataError() from None

        return NegotiationDebrief(
            repeated_strengths=payload.repeated_strengths,
            repeated_weaknesses=payload.repeated_weaknesses,
            key_missed_opportunities=payload.key_missed_opportunities,
            recurring_risks=payload.recurring_risks,
            overall_assessment=payload.overall_assessment,
            confidence=payload.confidence,
        )


class DebriefService:
    def __init__(
        self,
        coach_observation_repository: CoachObservationRepository,
        extractor: DebriefExtractor,
        debrief_repository: NegotiationDebriefRepository,
    ) -> None:
        self._coach_observation_repository = coach_observation_repository
        self._extractor = extractor
        self._debrief_repository = debrief_repository

    def generate_for_session(
        self,
        session_id: UUID,
    ) -> NegotiationDebriefRecord:
        observations = self._coach_observation_repository.list_by_session(session_id)
        if not observations:
            raise NoCoachObservationsError()

        debrief = self._extractor.extract(observations)
        record = NegotiationDebriefRecord(
            id=uuid4(),
            session_id=session_id,
            debrief=debrief,
            observation_count=len(observations),
            created_at=datetime.now(UTC),
        )
        return self._debrief_repository.create(record)
