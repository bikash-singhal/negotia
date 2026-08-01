from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.negotiation import NegotiationSessionModel
from app.database.repositories._session import (
    RepositorySessionManager,
    SessionFactory,
)
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError


def negotiation_to_model(session: NegotiationSession) -> NegotiationSessionModel:
    return NegotiationSessionModel(
        id=session.id,
        user_id=session.user_id,
        scenario_id=session.scenario_id,
        status=session.status.value,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def negotiation_to_domain(model: NegotiationSessionModel) -> NegotiationSession:
    return NegotiationSession(
        id=model.id,
        user_id=model.user_id,
        scenario_id=model.scenario_id,
        status=NegotiationStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLNegotiationRepository(NegotiationRepository):
    def __init__(
        self,
        session_factory: SessionFactory | None = None,
        *,
        session: Session | None = None,
    ) -> None:
        self._session_manager = RepositorySessionManager(
            session_factory,
            session=session,
        )

    def create(self, session: NegotiationSession) -> NegotiationSession:
        with self._session_manager.session_scope() as database_session:
            model = negotiation_to_model(session)
            database_session.add(model)
            try:
                self._session_manager.finish_write(database_session, [model])
            except SQLAlchemyError:
                self._session_manager.rollback_owned_transaction(database_session)
                raise

            return negotiation_to_domain(model)

    def get_for_user(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationSession | None:
        with self._session_manager.session_scope() as database_session:
            model = database_session.scalar(
                select(NegotiationSessionModel).where(
                    NegotiationSessionModel.id == session_id,
                    NegotiationSessionModel.user_id == user_id,
                )
            )
            return None if model is None else negotiation_to_domain(model)

    def get_for_update_for_user(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationSession | None:
        with self._session_manager.session_scope() as database_session:
            model = database_session.scalar(
                select(NegotiationSessionModel)
                .where(
                    NegotiationSessionModel.id == session_id,
                    NegotiationSessionModel.user_id == user_id,
                )
                .with_for_update()
            )
            return None if model is None else negotiation_to_domain(model)

    def list_for_user(self, user_id: UUID) -> list[NegotiationSession]:
        with self._session_manager.session_scope() as database_session:
            models = database_session.scalars(
                select(NegotiationSessionModel)
                .where(NegotiationSessionModel.user_id == user_id)
                .order_by(
                    NegotiationSessionModel.created_at,
                    NegotiationSessionModel.id,
                )
            ).all()
            return [negotiation_to_domain(model) for model in models]

    def update_for_user(
        self,
        session: NegotiationSession,
        user_id: UUID,
    ) -> NegotiationSession:
        with self._session_manager.session_scope() as database_session:
            model = database_session.scalar(
                select(NegotiationSessionModel).where(
                    NegotiationSessionModel.id == session.id,
                    NegotiationSessionModel.user_id == user_id,
                )
            )
            if model is None:
                raise NegotiationSessionNotFoundError(session.id)

            if session.user_id != user_id:
                raise NegotiationSessionNotFoundError(session.id)
            model.user_id = session.user_id
            model.scenario_id = session.scenario_id
            model.status = session.status.value
            model.created_at = session.created_at
            model.updated_at = session.updated_at
            try:
                self._session_manager.finish_write(database_session, [model])
            except SQLAlchemyError:
                self._session_manager.rollback_owned_transaction(database_session)
                raise

            return negotiation_to_domain(model)
