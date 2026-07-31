import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    ValidationError,
    model_validator,
)

from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.strategy.exceptions import (
    EmptyStrategyResponseError,
    InvalidStrategyDataError,
    InvalidStrategyJsonError,
    NegotiationDebriefNotFoundError,
)
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
    NegotiationTactic,
)
from app.domains.strategy.repository import NegotiationStrategyRepository
from app.llm.provider import LLMProvider
from app.prompts.strategy import StrategyPromptBuilder


class _NegotiationTacticPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    priority: PositiveInt
    title: str
    rationale: str
    actions: list[str]
    example_language: list[str]
    success_indicator: str


class _NegotiationStrategyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    primary_objective: str
    expected_outcome: str
    prioritized_tactics: list[_NegotiationTacticPayload]
    long_term_skills: list[str]
    preparation_checklist: list[str]
    avoid_next_time: list[str]
    confidence: str

    @model_validator(mode="after")
    def validate_unique_priorities(self) -> "_NegotiationStrategyPayload":
        priorities = [tactic.priority for tactic in self.prioritized_tactics]
        if len(priorities) != len(set(priorities)):
            raise ValueError("Tactic priorities must be unique.")
        return self


class StrategyExtractor:
    def __init__(
        self,
        prompt_builder: StrategyPromptBuilder,
        llm_provider: LLMProvider,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider

    def extract(
        self,
        debrief_record: NegotiationDebriefRecord,
    ) -> NegotiationStrategy:
        response = self._llm_provider.generate(
            system_prompt=self._prompt_builder.build_system_prompt(),
            user_prompt=self._prompt_builder.build_user_prompt(debrief_record),
        ).strip()
        if not response:
            raise EmptyStrategyResponseError()

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            raise InvalidStrategyJsonError() from None

        try:
            payload = _NegotiationStrategyPayload.model_validate(data)
        except ValidationError:
            raise InvalidStrategyDataError() from None

        tactics = sorted(
            (
                NegotiationTactic(
                    priority=tactic.priority,
                    title=tactic.title,
                    rationale=tactic.rationale,
                    actions=tactic.actions,
                    example_language=tactic.example_language,
                    success_indicator=tactic.success_indicator,
                )
                for tactic in payload.prioritized_tactics
            ),
            key=lambda tactic: tactic.priority,
        )
        return NegotiationStrategy(
            primary_objective=payload.primary_objective,
            expected_outcome=payload.expected_outcome,
            prioritized_tactics=tactics,
            long_term_skills=payload.long_term_skills,
            preparation_checklist=payload.preparation_checklist,
            avoid_next_time=payload.avoid_next_time,
            confidence=payload.confidence,
        )


class StrategyService:
    def __init__(
        self,
        debrief_repository: NegotiationDebriefRepository,
        extractor: StrategyExtractor,
        strategy_repository: NegotiationStrategyRepository,
    ) -> None:
        self._debrief_repository = debrief_repository
        self._extractor = extractor
        self._strategy_repository = strategy_repository

    def generate_for_session(
        self,
        session_id: UUID,
    ) -> NegotiationStrategyRecord:
        return self._strategy_repository.create(self.prepare_for_session(session_id))

    def prepare_for_session(
        self,
        session_id: UUID,
        debrief_record: NegotiationDebriefRecord | None = None,
    ) -> NegotiationStrategyRecord:
        if debrief_record is None:
            debrief_record = self._debrief_repository.get_by_session(session_id)
        if debrief_record is None:
            raise NegotiationDebriefNotFoundError(session_id)
        if debrief_record.session_id != session_id:
            raise NegotiationDebriefNotFoundError(session_id)

        strategy = self._extractor.extract(debrief_record)
        record = NegotiationStrategyRecord(
            id=uuid4(),
            session_id=session_id,
            debrief_id=debrief_record.id,
            strategy=strategy,
            created_at=datetime.now(UTC),
        )
        return record

    def get_for_session(
        self,
        session_id: UUID,
    ) -> NegotiationStrategyRecord | None:
        return self._strategy_repository.get_by_session(session_id)
