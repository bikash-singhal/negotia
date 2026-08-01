from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.database.repositories.user import SQLUserRepository
from app.database.session import engine
from tests.ownership import TEST_USER

SessionFactory = Callable[[], Session]


@pytest.fixture
def database_session_factory() -> Iterator[SessionFactory]:
    connection: Connection = engine.connect()
    transaction = connection.begin()
    connection.execute(text("TRUNCATE TABLE users, scenarios CASCADE"))

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


@pytest.fixture(autouse=True)
def persisted_test_owner(database_session_factory: SessionFactory) -> None:
    SQLUserRepository(database_session_factory).create(TEST_USER)
