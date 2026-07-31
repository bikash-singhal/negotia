from collections.abc import Callable
from copy import deepcopy
from types import TracebackType
from typing import Self
from uuid import UUID

from app.database.unit_of_work import CompletionUnitOfWork
from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.memory.models import NegotiatorMemoryRecord
from app.domains.memory.repository import NegotiatorMemoryRepository
from app.domains.negotiation.models import NegotiationSession
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.strategy.models import NegotiationStrategyRecord
from app.domains.strategy.repository import NegotiationStrategyRepository

type RepositorySnapshot = tuple[
    dict[UUID, NegotiationSession],
    dict[UUID, NegotiationDebriefRecord],
    dict[UUID, NegotiationStrategyRecord],
    list[NegotiatorMemoryRecord],
    dict[UUID, NegotiatorMemoryRecord],
]


class InMemoryCompletionUnitOfWork(CompletionUnitOfWork):
    def __init__(
        self,
        negotiation_repository: NegotiationRepository,
        debrief_repository: NegotiationDebriefRepository,
        strategy_repository: NegotiationStrategyRepository,
        memory_repository: NegotiatorMemoryRepository,
    ) -> None:
        self._negotiation_repository = negotiation_repository
        self._debrief_repository = debrief_repository
        self._strategy_repository = strategy_repository
        self._memory_repository = memory_repository
        self._snapshot: RepositorySnapshot | None = None

    @property
    def negotiation_repository(self) -> NegotiationRepository:
        return self._negotiation_repository

    @property
    def debrief_repository(self) -> NegotiationDebriefRepository:
        return self._debrief_repository

    @property
    def strategy_repository(self) -> NegotiationStrategyRepository:
        return self._strategy_repository

    @property
    def memory_repository(self) -> NegotiatorMemoryRepository:
        return self._memory_repository

    def __enter__(self) -> Self:
        self._snapshot = (
            deepcopy(self._negotiation_repository._sessions),
            deepcopy(self._debrief_repository._records),
            deepcopy(self._strategy_repository._records),
            deepcopy(self._memory_repository._records),
            deepcopy(self._memory_repository._records_by_trigger_session),
        )
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exception_type is not None:
            self.rollback()

    def commit(self) -> None:
        self._snapshot = None

    def rollback(self) -> None:
        if self._snapshot is None:
            return
        (
            negotiation_sessions,
            debrief_records,
            strategy_records,
            memory_records,
            memory_records_by_trigger,
        ) = self._snapshot
        self._negotiation_repository._sessions = negotiation_sessions
        self._debrief_repository._records = debrief_records
        self._strategy_repository._records = strategy_records
        self._memory_repository._records = memory_records
        self._memory_repository._records_by_trigger_session = memory_records_by_trigger
        self._snapshot = None


def build_in_memory_unit_of_work_factory(
    negotiation_repository: NegotiationRepository,
    debrief_repository: NegotiationDebriefRepository,
    strategy_repository: NegotiationStrategyRepository,
    memory_repository: NegotiatorMemoryRepository,
) -> Callable[[], CompletionUnitOfWork]:
    return lambda: InMemoryCompletionUnitOfWork(
        negotiation_repository,
        debrief_repository,
        strategy_repository,
        memory_repository,
    )
