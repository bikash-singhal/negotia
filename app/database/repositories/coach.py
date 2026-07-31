from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.coach import CoachObservationModel
from app.database.session import SessionLocal
from app.domains.coach.exceptions import CoachObservationAlreadyExistsError
from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.coach.repository import CoachObservationRepository

SessionFactory = Callable[[], Session]


def coach_observation_to_model(
    record: CoachObservationRecord,
) -> CoachObservationModel:
    return CoachObservationModel(
        id=record.id,
        session_id=record.session_id,
        user_turn_id=record.user_turn_id,
        opponent_turn_id=record.opponent_turn_id,
        strengths=list(record.observation.strengths),
        weaknesses=list(record.observation.weaknesses),
        missed_opportunities=list(record.observation.missed_opportunities),
        risk_signals=list(record.observation.risk_signals),
        confidence=record.observation.confidence,
        created_at=record.created_at,
    )


def coach_observation_to_domain(
    model: CoachObservationModel,
) -> CoachObservationRecord:
    return CoachObservationRecord(
        id=model.id,
        session_id=model.session_id,
        user_turn_id=model.user_turn_id,
        opponent_turn_id=model.opponent_turn_id,
        observation=CoachObservation(
            strengths=list(model.strengths),
            weaknesses=list(model.weaknesses),
            missed_opportunities=list(model.missed_opportunities),
            risk_signals=list(model.risk_signals),
            confidence=model.confidence,
        ),
        created_at=model.created_at,
    )


class SQLCoachObservationRepository(CoachObservationRepository):
    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    def create(self, record: CoachObservationRecord) -> CoachObservationRecord:
        with self._session_factory() as database_session:
            try:
                duplicate_id = database_session.scalar(
                    select(CoachObservationModel.id).where(
                        CoachObservationModel.user_turn_id == record.user_turn_id,
                        CoachObservationModel.opponent_turn_id
                        == record.opponent_turn_id,
                    )
                )
                if duplicate_id is not None:
                    raise CoachObservationAlreadyExistsError(
                        record.user_turn_id,
                        record.opponent_turn_id,
                    )

                model = coach_observation_to_model(record)
                database_session.add(model)
                database_session.commit()
                database_session.refresh(model)
            except SQLAlchemyError:
                database_session.rollback()
                raise

            return coach_observation_to_domain(model)

    def list_by_session(
        self,
        session_id: UUID,
    ) -> list[CoachObservationRecord]:
        with self._session_factory() as database_session:
            models = database_session.scalars(
                select(CoachObservationModel)
                .where(CoachObservationModel.session_id == session_id)
                .order_by(
                    CoachObservationModel.created_at,
                    CoachObservationModel.id,
                )
            ).all()
            return [coach_observation_to_domain(model) for model in models]
