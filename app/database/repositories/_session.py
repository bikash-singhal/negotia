from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.database.session import SessionLocal

type SessionFactory = Callable[[], Session]


class RepositorySessionManager:
    def __init__(
        self,
        session_factory: SessionFactory | None = None,
        *,
        session: Session | None = None,
    ) -> None:
        if session_factory is not None and session is not None:
            raise ValueError("Provide either a session factory or a shared Session.")

        self._session_factory = session_factory or SessionLocal
        self._shared_session = session

    @property
    def shared_session(self) -> Session | None:
        return self._shared_session

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        if self._shared_session is not None:
            yield self._shared_session
            return

        with self._session_factory() as database_session:
            yield database_session

    def finish_write(
        self,
        database_session: Session,
        models: Iterable[object],
    ) -> None:
        if self._shared_session is not None:
            database_session.flush()
            return

        database_session.commit()
        for model in models:
            database_session.refresh(model)

    def rollback_owned_transaction(self, database_session: Session) -> None:
        if self._shared_session is None:
            database_session.rollback()
