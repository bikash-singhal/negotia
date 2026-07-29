from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.schemas import NegotiationSessionCreate


class NegotiationService:
    def __init__(self, repository: NegotiationRepository) -> None:
        self._repository = repository

    def create_session(
        self,
        request: NegotiationSessionCreate,
    ) -> NegotiationSession:
        now = datetime.now(UTC)
        session = NegotiationSession(
            id=uuid4(),
            scenario_id=request.scenario_id,
            status=NegotiationStatus.CREATED,
            created_at=now,
            updated_at=now,
        )

        return self._repository.create(session)

    def get_session(self, session_id: UUID) -> NegotiationSession | None:
        return self._repository.get(session_id)

    def list_sessions(self) -> list[NegotiationSession]:
        return self._repository.list()
