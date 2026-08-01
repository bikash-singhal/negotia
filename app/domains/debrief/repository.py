from uuid import UUID

from app.domains.debrief.exceptions import (
    NegotiationDebriefAlreadyExistsError,
)
from app.domains.debrief.models import NegotiationDebriefRecord


class NegotiationDebriefRepository:
    def __init__(self) -> None:
        self._records: dict[UUID, NegotiationDebriefRecord] = {}
        self._user_ids: dict[UUID, UUID] = {}

    def create(
        self,
        record: NegotiationDebriefRecord,
        user_id: UUID,
    ) -> NegotiationDebriefRecord:
        if record.session_id in self._records:
            raise NegotiationDebriefAlreadyExistsError(record.session_id)

        self._records[record.session_id] = record
        self._user_ids[record.session_id] = user_id
        return record

    def get_by_session_for_user(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationDebriefRecord | None:
        if self._user_ids.get(session_id) != user_id:
            return None
        return self._records.get(session_id)
