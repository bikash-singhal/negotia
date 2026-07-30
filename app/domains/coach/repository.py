from uuid import UUID

from app.domains.coach.exceptions import CoachObservationAlreadyExistsError
from app.domains.coach.models import CoachObservationRecord


class CoachObservationRepository:
    def __init__(self) -> None:
        self._records: list[CoachObservationRecord] = []

    def create(self, record: CoachObservationRecord) -> CoachObservationRecord:
        if any(
            existing.user_turn_id == record.user_turn_id
            and existing.opponent_turn_id == record.opponent_turn_id
            for existing in self._records
        ):
            raise CoachObservationAlreadyExistsError(
                record.user_turn_id,
                record.opponent_turn_id,
            )

        self._records.append(record)
        return record

    def list_by_session(
        self,
        session_id: UUID,
    ) -> list[CoachObservationRecord]:
        return [record for record in self._records if record.session_id == session_id]
