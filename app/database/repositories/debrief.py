from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.debrief import NegotiationDebriefModel
from app.database.session import SessionLocal
from app.domains.debrief.exceptions import NegotiationDebriefAlreadyExistsError
from app.domains.debrief.models import NegotiationDebrief, NegotiationDebriefRecord
from app.domains.debrief.repository import NegotiationDebriefRepository

SessionFactory = Callable[[], Session]


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
    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    def create(
        self,
        record: NegotiationDebriefRecord,
    ) -> NegotiationDebriefRecord:
        with self._session_factory() as database_session:
            try:
                duplicate_id = database_session.scalar(
                    select(NegotiationDebriefModel.id).where(
                        NegotiationDebriefModel.session_id == record.session_id
                    )
                )
                if duplicate_id is not None:
                    raise NegotiationDebriefAlreadyExistsError(record.session_id)

                model = negotiation_debrief_to_model(record)
                database_session.add(model)
                database_session.commit()
                database_session.refresh(model)
            except SQLAlchemyError:
                database_session.rollback()
                raise

            return negotiation_debrief_to_domain(model)

    def get_by_session(
        self,
        session_id: UUID,
    ) -> NegotiationDebriefRecord | None:
        with self._session_factory() as database_session:
            model = database_session.scalar(
                select(NegotiationDebriefModel).where(
                    NegotiationDebriefModel.session_id == session_id
                )
            )
            return None if model is None else negotiation_debrief_to_domain(model)
