from datetime import UTC, datetime
from uuid import UUID

from app.domains.user.models import User

TEST_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = UUID("22222222-2222-4222-8222-222222222222")

TEST_USER = User(
    id=TEST_USER_ID,
    username="test-owner",
    password_hash="not-used-by-domain-tests",
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
)
