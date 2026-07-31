from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.negotiation import NegotiationSessionModel
from app.database.session import SessionLocal
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError

SessionFactory = Callable[[], Session]


def negotiation_to_model(session: NegotiationSession) -> NegotiationSessionModel:
    return NegotiationSessionModel(
        id=session.id,
        scenario_id=session.scenario_id,
        status=session.status.value,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def negotiation_to_domain(model: NegotiationSessionModel) -> NegotiationSession:
    return NegotiationSession(
        id=model.id,
        scenario_id=model.scenario_id,
        status=NegotiationStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLNegotiationRepository(NegotiationRepository):
    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    def create(self, session: NegotiationSession) -> NegotiationSession:
        with self._session_factory() as database_session:
            model = negotiation_to_model(session)
            database_session.add(model)
            try:
                database_session.commit()
                database_session.refresh(model)
            except SQLAlchemyError:
                database_session.rollback()
                raise

            return negotiation_to_domain(model)

    def get(self, session_id: UUID) -> NegotiationSession | None:
        with self._session_factory() as database_session:
            model = database_session.get(NegotiationSessionModel, session_id)
            return None if model is None else negotiation_to_domain(model)

    def list(self) -> list[NegotiationSession]:
        with self._session_factory() as database_session:
            models = database_session.scalars(
                select(NegotiationSessionModel).order_by(
                    NegotiationSessionModel.created_at,
                    NegotiationSessionModel.id,
                )
            ).all()
            return [negotiation_to_domain(model) for model in models]

    def update(self, session: NegotiationSession) -> NegotiationSession:
        with self._session_factory() as database_session:
            model = database_session.get(NegotiationSessionModel, session.id)
            if model is None:
                raise NegotiationSessionNotFoundError(session.id)

            model.scenario_id = session.scenario_id
            model.status = session.status.value
            model.created_at = session.created_at
            model.updated_at = session.updated_at
            try:
                database_session.commit()
                database_session.refresh(model)
            except SQLAlchemyError:
                database_session.rollback()
                raise

            return negotiation_to_domain(model)
