import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, ValidationError

from app.domains.adaptive_context.models import AdaptiveContext
from app.domains.coach.exceptions import (
    EmptyCoachObservationResponseError,
    InvalidCoachExchangeError,
    InvalidCoachObservationDataError,
    InvalidCoachObservationJsonError,
)
from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.coach.repository import CoachObservationRepository
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.llm.observability import generate_with_observability
from app.llm.provider import LLMProvider
from app.prompts.coach import CoachPromptBuilder
from app.services.adaptive_context import AdaptiveContextService

logger = logging.getLogger(__name__)


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

    def extract(
        self,
        turns: list[NegotiationTurn],
        adaptive_context: AdaptiveContext | None = None,
    ) -> CoachObservation:
        response = generate_with_observability(
            self._llm_provider,
            logger,
            "coach_observation_extraction",
            system_prompt=self._prompt_builder.build_system_prompt(adaptive_context),
            user_prompt=self._prompt_builder.build_user_prompt(turns),
            session_id=turns[0].session_id if turns else None,
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
    def __init__(
        self,
        extractor: CoachObservationExtractor,
        repository: CoachObservationRepository,
        adaptive_context_service: AdaptiveContextService,
    ) -> None:
        self._extractor = extractor
        self._repository = repository
        self._adaptive_context_service = adaptive_context_service

    def analyze_exchange(
        self,
        session_id: UUID,
        turns: list[NegotiationTurn],
        user_turn: NegotiationTurn,
        opponent_turn: NegotiationTurn,
    ) -> CoachObservationRecord:
        self._validate_exchange(
            session_id,
            turns,
            user_turn,
            opponent_turn,
        )
        adaptive_context = self._adaptive_context_service.get_context()
        observation = self._extractor.extract(turns, adaptive_context)
        record = CoachObservationRecord(
            id=uuid4(),
            session_id=session_id,
            user_turn_id=user_turn.id,
            opponent_turn_id=opponent_turn.id,
            observation=observation,
            created_at=datetime.now(UTC),
        )

        return self._repository.create(record)

    @staticmethod
    def _validate_exchange(
        session_id: UUID,
        turns: list[NegotiationTurn],
        user_turn: NegotiationTurn,
        opponent_turn: NegotiationTurn,
    ) -> None:
        if (
            not turns
            or any(turn.session_id != session_id for turn in turns)
            or user_turn.session_id != session_id
            or opponent_turn.session_id != session_id
            or user_turn.speaker is not NegotiationTurnSpeaker.USER
            or opponent_turn.speaker is not NegotiationTurnSpeaker.OPPONENT
            or turns != sorted(turns, key=lambda turn: turn.turn_number)
            or turns[-1].id != opponent_turn.id
        ):
            raise InvalidCoachExchangeError()

        latest_user_turn = next(
            (
                turn
                for turn in reversed(turns[:-1])
                if turn.speaker is NegotiationTurnSpeaker.USER
            ),
            None,
        )
        if latest_user_turn is None or latest_user_turn.id != user_turn.id:
            raise InvalidCoachExchangeError()
