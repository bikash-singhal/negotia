from uuid import UUID

from app.domains.strategy.exceptions import (
    NegotiationStrategyAlreadyExistsError,
)
from app.domains.strategy.models import NegotiationStrategyRecord


class NegotiationStrategyRepository:
    def __init__(self) -> None:
        self._records: dict[UUID, NegotiationStrategyRecord] = {}

    def create(
        self,
        record: NegotiationStrategyRecord,
    ) -> NegotiationStrategyRecord:
        if record.session_id in self._records:
            raise NegotiationStrategyAlreadyExistsError(record.session_id)

        self._records[record.session_id] = record
        return record

    def get_by_session(
        self,
        session_id: UUID,
    ) -> NegotiationStrategyRecord | None:
        return self._records.get(session_id)

    def list_all(self) -> list[NegotiationStrategyRecord]:
        return list(self._records.values())
