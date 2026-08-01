from uuid import UUID

from app.domains.strategy.exceptions import (
    NegotiationStrategyAlreadyExistsError,
)
from app.domains.strategy.models import NegotiationStrategyRecord


class NegotiationStrategyRepository:
    def __init__(self) -> None:
        self._records: dict[UUID, NegotiationStrategyRecord] = {}
        self._user_ids: dict[UUID, UUID] = {}

    def create(
        self,
        record: NegotiationStrategyRecord,
        user_id: UUID,
    ) -> NegotiationStrategyRecord:
        if record.session_id in self._records:
            raise NegotiationStrategyAlreadyExistsError(record.session_id)

        self._records[record.session_id] = record
        self._user_ids[record.session_id] = user_id
        return record

    def get_by_session_for_user(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationStrategyRecord | None:
        if self._user_ids.get(session_id) != user_id:
            return None
        return self._records.get(session_id)

    def list_for_user(self, user_id: UUID) -> list[NegotiationStrategyRecord]:
        return [
            record
            for session_id, record in self._records.items()
            if self._user_ids.get(session_id) == user_id
        ]
