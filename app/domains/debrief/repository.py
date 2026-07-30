from uuid import UUID

from app.domains.debrief.exceptions import (
    NegotiationDebriefAlreadyExistsError,
)
from app.domains.debrief.models import NegotiationDebriefRecord


class NegotiationDebriefRepository:
    def __init__(self) -> None:
        self._records: dict[UUID, NegotiationDebriefRecord] = {}

    def create(
        self,
        record: NegotiationDebriefRecord,
    ) -> NegotiationDebriefRecord:
        if record.session_id in self._records:
            raise NegotiationDebriefAlreadyExistsError(record.session_id)

        self._records[record.session_id] = record
        return record

    def get_by_session(
        self,
        session_id: UUID,
    ) -> NegotiationDebriefRecord | None:
        return self._records.get(session_id)
