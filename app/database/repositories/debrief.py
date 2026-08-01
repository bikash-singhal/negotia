from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.debrief import NegotiationDebriefModel
from app.database.models.negotiation import NegotiationSessionModel
from app.database.repositories._session import (
    RepositorySessionManager,
    SessionFactory,
)
from app.domains.debrief.exceptions import NegotiationDebriefAlreadyExistsError
from app.domains.debrief.models import NegotiationDebrief, NegotiationDebriefRecord
from app.domains.debrief.repository import NegotiationDebriefRepository
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError


def negotiation_debrief_to_model(
    record: NegotiationDebriefRecord,
) -> NegotiationDebriefModel:
    return NegotiationDebriefModel(
        id=record.id,
        session_id=record.session_id,
        repeated_strengths=list(record.debrief.repeated_strengths),
        repeated_weaknesses=list(record.debrief.repeated_weaknesses),
        key_missed_opportunities=list(record.debrief.key_missed_opportunities),
        recurring_risks=list(record.debrief.recurring_risks),
        overall_assessment=record.debrief.overall_assessment,
        confidence=record.debrief.confidence,
        observation_count=record.observation_count,
        created_at=record.created_at,
    )


def negotiation_debrief_to_domain(
    model: NegotiationDebriefModel,
) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=model.id,
        session_id=model.session_id,
        debrief=NegotiationDebrief(
            repeated_strengths=list(model.repeated_strengths),
            repeated_weaknesses=list(model.repeated_weaknesses),
            key_missed_opportunities=list(model.key_missed_opportunities),
            recurring_risks=list(model.recurring_risks),
            overall_assessment=model.overall_assessment,
            confidence=model.confidence,
        ),
        observation_count=model.observation_count,
        created_at=model.created_at,
    )


class SQLNegotiationDebriefRepository(NegotiationDebriefRepository):
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

    def create(
        self,
        record: NegotiationDebriefRecord,
        user_id: UUID,
    ) -> NegotiationDebriefRecord:
        with self._session_manager.session_scope() as database_session:
            try:
                session_exists = database_session.scalar(
                    select(NegotiationSessionModel.id).where(
                        NegotiationSessionModel.id == record.session_id,
                        NegotiationSessionModel.user_id == user_id,
                    )
                )
                if session_exists is None:
                    raise NegotiationSessionNotFoundError(record.session_id)
                duplicate_id = database_session.scalar(
                    select(NegotiationDebriefModel.id).where(
                        NegotiationDebriefModel.session_id == record.session_id
                    )
                )
                if duplicate_id is not None:
                    raise NegotiationDebriefAlreadyExistsError(record.session_id)

                model = negotiation_debrief_to_model(record)
                database_session.add(model)
                self._session_manager.finish_write(database_session, [model])
            except SQLAlchemyError:
                self._session_manager.rollback_owned_transaction(database_session)
                raise

            return negotiation_debrief_to_domain(model)

    def get_by_session_for_user(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> NegotiationDebriefRecord | None:
        with self._session_manager.session_scope() as database_session:
            model = database_session.scalar(
                select(NegotiationDebriefModel)
                .join(
                    NegotiationSessionModel,
                    NegotiationSessionModel.id == NegotiationDebriefModel.session_id,
                )
                .where(
                    NegotiationDebriefModel.session_id == session_id,
                    NegotiationSessionModel.user_id == user_id,
                )
            )
            return None if model is None else negotiation_debrief_to_domain(model)
