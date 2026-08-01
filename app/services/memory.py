import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

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
from app.llm.observability import generate_with_observability
from app.llm.provider import LLMProvider
from app.llm.structured_json import parse_structured_json
from app.prompts.memory import MemoryPromptBuilder

logger = logging.getLogger(__name__)


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
        raw_response = generate_with_observability(
            self._llm_provider,
            logger,
            "memory_extraction",
            system_prompt=self._prompt_builder.build_system_prompt(),
            user_prompt=self._prompt_builder.build_user_prompt(
                ordered_debriefs,
                ordered_strategies,
            ),
            temperature=0.0,
        )
        memory = parse_structured_json(
            raw_response,
            NegotiatorMemory,
            logger=logger,
            operation="memory_extraction",
            empty_response_error=EmptyMemoryResponseError,
            invalid_json_error=InvalidMemoryJsonError,
            invalid_data_error=InvalidMemoryDataError,
        )

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
        debrief_records, strategy_records = self._load_artifact_history()
        if len(strategy_records) < 2:
            raise InsufficientMemoryHistoryError(len(strategy_records))

        return self._extract_and_persist(
            debrief_records,
            strategy_records,
            trigger_session_id=None,
        )

    def generate_for_session(
        self,
        session_id: UUID,
    ) -> NegotiatorMemoryRecord | None:
        existing_record = self._memory_repository.get_by_trigger_session(session_id)
        if existing_record is not None:
            return existing_record

        debrief_records, strategy_records = self._load_artifact_history()
        if len(strategy_records) < 2:
            return None

        return self._memory_repository.create(
            self._prepare_record(
                debrief_records,
                strategy_records,
                trigger_session_id=session_id,
            )
        )

    def prepare_for_session(
        self,
        session_id: UUID,
        debrief_record: NegotiationDebriefRecord,
        strategy_record: NegotiationStrategyRecord,
    ) -> NegotiatorMemoryRecord | None:
        debrief_records, strategy_records = self._load_artifact_history(
            current_debrief=debrief_record,
            current_strategy=strategy_record,
        )
        if len(strategy_records) < 2:
            return None

        return self._prepare_record(
            debrief_records,
            strategy_records,
            trigger_session_id=session_id,
        )

    def get_by_trigger_session(
        self,
        session_id: UUID,
    ) -> NegotiatorMemoryRecord | None:
        return self._memory_repository.get_by_trigger_session(session_id)

    def get_latest(self) -> NegotiatorMemoryRecord | None:
        return self._memory_repository.get_latest()

    def list_versions(self) -> list[NegotiatorMemoryRecord]:
        return self._memory_repository.list_all()

    def _load_artifact_history(
        self,
        *,
        current_debrief: NegotiationDebriefRecord | None = None,
        current_strategy: NegotiationStrategyRecord | None = None,
    ) -> tuple[
        list[NegotiationDebriefRecord],
        list[NegotiationStrategyRecord],
    ]:
        strategy_records = self._strategy_repository.list_all()
        if current_strategy is not None and all(
            record.session_id != current_strategy.session_id
            for record in strategy_records
        ):
            strategy_records.append(current_strategy)

        debrief_records: list[NegotiationDebriefRecord] = []
        for strategy_record in strategy_records:
            if (
                current_debrief is not None
                and current_debrief.session_id == strategy_record.session_id
            ):
                debrief_record = current_debrief
            else:
                debrief_record = self._debrief_repository.get_by_session(
                    strategy_record.session_id
                )
            if debrief_record is None:
                raise MismatchedMemoryArtifactSetError()
            if strategy_record.debrief_id != debrief_record.id:
                raise MismatchedMemoryArtifactSetError()
            debrief_records.append(debrief_record)
        return debrief_records, strategy_records

    def _extract_and_persist(
        self,
        debrief_records: list[NegotiationDebriefRecord],
        strategy_records: list[NegotiationStrategyRecord],
        trigger_session_id: UUID | None,
    ) -> NegotiatorMemoryRecord:
        return self._memory_repository.create(
            self._prepare_record(
                debrief_records,
                strategy_records,
                trigger_session_id,
            )
        )

    def _prepare_record(
        self,
        debrief_records: list[NegotiationDebriefRecord],
        strategy_records: list[NegotiationStrategyRecord],
        trigger_session_id: UUID | None,
    ) -> NegotiatorMemoryRecord:
        memory = self._extractor.extract(debrief_records, strategy_records)
        source_session_ids = tuple(
            sorted(
                (record.session_id for record in strategy_records),
                key=str,
            )
        )
        record = NegotiatorMemoryRecord(
            id=uuid4(),
            trigger_session_id=trigger_session_id,
            memory=memory,
            source_session_ids=source_session_ids,
            created_at=datetime.now(UTC),
        )
        return record
