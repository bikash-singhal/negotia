from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.database.session import engine

SessionFactory = Callable[[], Session]


@pytest.fixture
def database_session_factory() -> Iterator[SessionFactory]:
    connection: Connection = engine.connect()
    transaction = connection.begin()
    connection.execute(text("TRUNCATE TABLE scenarios CASCADE"))

    def create_session() -> Session:
        return Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )

    try:
        yield create_session
    finally:
        if transaction.is_active:
            transaction.rollback()
        connection.close()
