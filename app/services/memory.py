import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.memory.exceptions import (
    DuplicateMemoryDebriefSessionError,
    DuplicateMemoryStrategySessionError,
    EmptyMemoryHistoryError,
    EmptyMemoryResponseError,
    InsufficientMemoryHistoryError,
    InvalidMemoryDataError,
    InvalidMemoryJsonError,
    MemorySessionsAnalyzedMismatchError,
    MismatchedMemoryArtifactSetError,
)
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.memory.repository import NegotiatorMemoryRepository
from app.domains.strategy.models import NegotiationStrategyRecord
from app.domains.strategy.repository import NegotiationStrategyRepository
from app.llm.provider import LLMProvider
from app.prompts.memory import MemoryPromptBuilder


class MemoryExtractor:
    def __init__(
        self,
        prompt_builder: MemoryPromptBuilder,
        llm_provider: LLMProvider,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider

    def extract(
        self,
        debrief_records: list[NegotiationDebriefRecord],
        strategy_records: list[NegotiationStrategyRecord],
    ) -> NegotiatorMemory:
        if not debrief_records and not strategy_records:
            raise EmptyMemoryHistoryError()

        self._reject_duplicate_debrief_sessions(debrief_records)
        self._reject_duplicate_strategy_sessions(strategy_records)

        debrief_session_ids = {record.session_id for record in debrief_records}
        strategy_session_ids = {record.session_id for record in strategy_records}
        if debrief_session_ids != strategy_session_ids:
            raise MismatchedMemoryArtifactSetError()

        ordered_debriefs = sorted(
            debrief_records,
            key=lambda record: str(record.session_id),
        )
        ordered_strategies = sorted(
            strategy_records,
            key=lambda record: str(record.session_id),
        )
        response = self._llm_provider.generate(
            system_prompt=self._prompt_builder.build_system_prompt(),
            user_prompt=self._prompt_builder.build_user_prompt(
                ordered_debriefs,
                ordered_strategies,
            ),
        ).strip()
        if not response:
            raise EmptyMemoryResponseError()

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            raise InvalidMemoryJsonError() from None

        try:
            memory = NegotiatorMemory.model_validate(data)
        except ValidationError:
            raise InvalidMemoryDataError() from None

        session_count = len(debrief_session_ids)
        if memory.sessions_analyzed != session_count:
            raise MemorySessionsAnalyzedMismatchError(
                expected=session_count,
                actual=memory.sessions_analyzed,
            )
        return memory

    @staticmethod
    def _reject_duplicate_debrief_sessions(
        records: list[NegotiationDebriefRecord],
    ) -> None:
        seen_session_ids: set[UUID] = set()
        for record in records:
            if record.session_id in seen_session_ids:
                raise DuplicateMemoryDebriefSessionError(record.session_id)
            seen_session_ids.add(record.session_id)

    @staticmethod
    def _reject_duplicate_strategy_sessions(
        records: list[NegotiationStrategyRecord],
    ) -> None:
        seen_session_ids: set[UUID] = set()
        for record in records:
            if record.session_id in seen_session_ids:
                raise DuplicateMemoryStrategySessionError(record.session_id)
            seen_session_ids.add(record.session_id)


class MemoryService:
    def __init__(
        self,
        debrief_repository: NegotiationDebriefRepository,
        strategy_repository: NegotiationStrategyRepository,
        extractor: MemoryExtractor,
        memory_repository: NegotiatorMemoryRepository,
    ) -> None:
        self._debrief_repository = debrief_repository
        self._strategy_repository = strategy_repository
        self._extractor = extractor
        self._memory_repository = memory_repository

    def generate(self) -> NegotiatorMemoryRecord:
        strategy_records = self._strategy_repository.list_all()
        debrief_records: list[NegotiationDebriefRecord] = []
        for strategy_record in strategy_records:
            debrief_record = self._debrief_repository.get_by_session(
                strategy_record.session_id
            )
            if debrief_record is None:
                raise MismatchedMemoryArtifactSetError()
            debrief_records.append(debrief_record)

        if len(strategy_records) < 2:
            raise InsufficientMemoryHistoryError(len(strategy_records))

        memory = self._extractor.extract(debrief_records, strategy_records)
        source_session_ids = tuple(
            sorted(
                (record.session_id for record in strategy_records),
                key=str,
            )
        )
        record = NegotiatorMemoryRecord(
            id=uuid4(),
            memory=memory,
            source_session_ids=source_session_ids,
            created_at=datetime.now(UTC),
        )
        return self._memory_repository.create(record)

    def get_latest(self) -> NegotiatorMemoryRecord | None:
        return self._memory_repository.get_latest()

    def list_versions(self) -> list[NegotiatorMemoryRecord]:
        return self._memory_repository.list_all()
