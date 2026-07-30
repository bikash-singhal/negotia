import json

from pydantic import BaseModel, ConfigDict, ValidationError

from app.domains.coach.exceptions import (
    EmptyCoachObservationResponseError,
    InvalidCoachObservationDataError,
    InvalidCoachObservationJsonError,
)
from app.domains.coach.models import CoachObservation
from app.domains.negotiation_turn.models import NegotiationTurn
from app.llm.provider import LLMProvider
from app.prompts.coach import CoachPromptBuilder


class _CoachObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strengths: list[str]
    weaknesses: list[str]
    missed_opportunities: list[str]
    risk_signals: list[str]
    confidence: str


class CoachObservationExtractor:
    def __init__(
        self,
        prompt_builder: CoachPromptBuilder,
        llm_provider: LLMProvider,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider

    def extract(self, turns: list[NegotiationTurn]) -> CoachObservation:
        response = self._llm_provider.generate(
            system_prompt=self._prompt_builder.build_system_prompt(),
            user_prompt=self._prompt_builder.build_user_prompt(turns),
        ).strip()
        if not response:
            raise EmptyCoachObservationResponseError()

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            raise InvalidCoachObservationJsonError() from None

        try:
            payload = _CoachObservationPayload.model_validate(data)
        except ValidationError:
            raise InvalidCoachObservationDataError() from None

        return CoachObservation(
            strengths=payload.strengths,
            weaknesses=payload.weaknesses,
            missed_opportunities=payload.missed_opportunities,
            risk_signals=payload.risk_signals,
            confidence=payload.confidence,
        )


class CoachService:
    def __init__(self, extractor: CoachObservationExtractor) -> None:
        self._extractor = extractor

    def analyze(self, turns: list[NegotiationTurn]) -> CoachObservation:
        return self._extractor.extract(turns)
