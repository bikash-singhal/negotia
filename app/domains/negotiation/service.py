from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.negotiation.exceptions import (
    InvalidNegotiationStatusTransitionError,
    ScenarioNotFoundError,
)
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation.schemas import NegotiationSessionCreate
from app.domains.negotiation_turn.exceptions import (
    NegotiationSessionNotFoundError,
)
from app.domains.scenario.repository import ScenarioRepository


class NegotiationService:
    def __init__(
        self,
        negotiation_repository: NegotiationRepository,
        scenario_repository: ScenarioRepository,
    ) -> None:
        self._negotiation_repository = negotiation_repository
        self._scenario_repository = scenario_repository

    def create_session(
        self,
        request: NegotiationSessionCreate,
    ) -> NegotiationSession:
        scenario = self._scenario_repository.get(request.scenario_id)
        if scenario is None:
            raise ScenarioNotFoundError(request.scenario_id)

        now = datetime.now(UTC)
        session = NegotiationSession(
            id=uuid4(),
            scenario_id=request.scenario_id,
            status=NegotiationStatus.CREATED,
            created_at=now,
            updated_at=now,
        )

        return self._negotiation_repository.create(session)

    def get_session(self, session_id: UUID) -> NegotiationSession | None:
        return self._negotiation_repository.get(session_id)

    def list_sessions(self) -> list[NegotiationSession]:
        return self._negotiation_repository.list()

    def validate_completion_transition(
        self,
        session_id: UUID,
    ) -> NegotiationSession:
        session = self._negotiation_repository.get(session_id)
        if session is None:
            raise NegotiationSessionNotFoundError(session_id)

        if session.status not in {
            NegotiationStatus.CREATED,
            NegotiationStatus.ACTIVE,
            NegotiationStatus.COMPLETED,
        }:
            raise InvalidNegotiationStatusTransitionError(
                session_id,
                session.status,
                NegotiationStatus.COMPLETED,
            )

        return session

    def mark_completed(self, session_id: UUID) -> NegotiationSession:
        session = self.validate_completion_transition(session_id)
        if session.status is NegotiationStatus.COMPLETED:
            return session

        session.status = NegotiationStatus.COMPLETED
        session.updated_at = datetime.now(UTC)
        return session
