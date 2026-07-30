from uuid import UUID

from app.domains.memory.exceptions import NegotiatorMemoryAlreadyExistsError
from app.domains.memory.models import NegotiatorMemoryRecord


class NegotiatorMemoryRepository:
    def __init__(self) -> None:
        self._records: list[NegotiatorMemoryRecord] = []
        self._records_by_trigger_session: dict[UUID, NegotiatorMemoryRecord] = {}

    def create(
        self,
        record: NegotiatorMemoryRecord,
    ) -> NegotiatorMemoryRecord:
        trigger_session_id = record.trigger_session_id
        if (
            trigger_session_id is not None
            and trigger_session_id in self._records_by_trigger_session
        ):
            raise NegotiatorMemoryAlreadyExistsError(trigger_session_id)

        self._records.append(record)
        if trigger_session_id is not None:
            self._records_by_trigger_session[trigger_session_id] = record
        return record

    def get_latest(self) -> NegotiatorMemoryRecord | None:
        if not self._records:
            return None
        return self._records[-1]

    def list_all(self) -> list[NegotiatorMemoryRecord]:
        return list(self._records)

    def get_by_trigger_session(
        self,
        session_id: UUID,
    ) -> NegotiatorMemoryRecord | None:
        return self._records_by_trigger_session.get(session_id)
