import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

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
from app.llm.observability import generate_with_observability
from app.llm.provider import LLMProvider
from app.llm.structured_json import parse_structured_json
from app.prompts.debrief import DebriefPromptBuilder

logger = logging.getLogger(__name__)


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

        raw_response = generate_with_observability(
            self._llm_provider,
            logger,
            "debrief_extraction",
            system_prompt=self._prompt_builder.build_system_prompt(),
            user_prompt=self._prompt_builder.build_user_prompt(observations),
            session_id=observations[0].session_id,
            temperature=0.0,
        )
        payload = parse_structured_json(
            raw_response,
            _NegotiationDebriefPayload,
            logger=logger,
            operation="debrief_extraction",
            session_id=observations[0].session_id,
            empty_response_error=EmptyDebriefResponseError,
            invalid_json_error=InvalidDebriefJsonError,
            invalid_data_error=InvalidDebriefDataError,
        )

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
        user_id: UUID,
    ) -> NegotiationDebriefRecord:
        return self._debrief_repository.create(
            self.prepare_for_session(session_id, user_id),
            user_id,
        )

    def prepare_for_session(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationDebriefRecord:
        observations = self._coach_observation_repository.list_by_session_for_user(
            session_id,
            user_id,
        )
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
        return record

    def get_for_session(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationDebriefRecord | None:
        return self._debrief_repository.get_by_session_for_user(session_id, user_id)
