from collections.abc import Iterator
from contextlib import contextmanager

from app.api.dependencies import get_current_user
from app.domains.user.models import User
from app.main import app
from tests.ownership import TEST_USER


@contextmanager
def authenticated_request() -> Iterator[User]:
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        yield TEST_USER
    finally:
        app.dependency_overrides.pop(get_current_user, None)
