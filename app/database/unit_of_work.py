from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from app.database.repositories._session import SessionFactory
from app.database.repositories.debrief import SQLNegotiationDebriefRepository
from app.database.repositories.memory import SQLNegotiatorMemoryRepository
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.strategy import SQLNegotiationStrategyRepository
from app.database.session import SessionLocal
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.memory.repository import NegotiatorMemoryRepository
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.strategy.repository import NegotiationStrategyRepository


class CompletionUnitOfWork(ABC):
    @property
    @abstractmethod
    def negotiation_repository(self) -> NegotiationRepository: ...

    @property
    @abstractmethod
    def debrief_repository(self) -> NegotiationDebriefRepository: ...

    @property
    @abstractmethod
    def strategy_repository(self) -> NegotiationStrategyRepository: ...

    @property
    @abstractmethod
    def memory_repository(self) -> NegotiatorMemoryRepository: ...

    @abstractmethod
    def __enter__(self) -> Self: ...

    @abstractmethod
    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...


type CompletionUnitOfWorkFactory = Callable[[], CompletionUnitOfWork]


class SQLCompletionUnitOfWork(CompletionUnitOfWork):
    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._has_entered = False
        self._transaction_finished = False
        self._negotiation_repository: SQLNegotiationRepository | None = None
        self._debrief_repository: SQLNegotiationDebriefRepository | None = None
        self._strategy_repository: SQLNegotiationStrategyRepository | None = None
        self._memory_repository: SQLNegotiatorMemoryRepository | None = None

    @property
    def negotiation_repository(self) -> SQLNegotiationRepository:
        if self._negotiation_repository is None:
            raise RuntimeError("The Unit of Work is not active.")
        return self._negotiation_repository

    @property
    def debrief_repository(self) -> SQLNegotiationDebriefRepository:
        if self._debrief_repository is None:
            raise RuntimeError("The Unit of Work is not active.")
        return self._debrief_repository

    @property
    def strategy_repository(self) -> SQLNegotiationStrategyRepository:
        if self._strategy_repository is None:
            raise RuntimeError("The Unit of Work is not active.")
        return self._strategy_repository

    @property
    def memory_repository(self) -> SQLNegotiatorMemoryRepository:
        if self._memory_repository is None:
            raise RuntimeError("The Unit of Work is not active.")
        return self._memory_repository

    def __enter__(self) -> Self:
        if self._has_entered:
            raise RuntimeError("A Unit of Work instance can only be entered once.")

        self._has_entered = True
        self._session = self._session_factory()
        self._negotiation_repository = SQLNegotiationRepository(session=self._session)
        self._debrief_repository = SQLNegotiationDebriefRepository(
            session=self._session
        )
        self._strategy_repository = SQLNegotiationStrategyRepository(
            session=self._session
        )
        self._memory_repository = SQLNegotiatorMemoryRepository(session=self._session)
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            if exception_type is not None or not self._transaction_finished:
                session.rollback()
        finally:
            session.close()
            self._session = None
            self._negotiation_repository = None
            self._debrief_repository = None
            self._strategy_repository = None
            self._memory_repository = None
            self._transaction_finished = False

    def commit(self) -> None:
        session = self._require_active_transaction()
        session.commit()
        self._transaction_finished = True

    def rollback(self) -> None:
        session = self._require_active_transaction()
        session.rollback()
        self._transaction_finished = True

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("The Unit of Work is not active.")
        return self._session

    def _require_active_transaction(self) -> Session:
        session = self._require_session()
        if self._transaction_finished:
            raise RuntimeError("The Unit of Work transaction has already finished.")
        return session
