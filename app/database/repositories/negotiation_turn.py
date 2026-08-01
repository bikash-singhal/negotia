from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.negotiation import NegotiationSessionModel
from app.database.models.negotiation_turn import NegotiationTurnModel
from app.database.session import SessionLocal
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.repository import NegotiationTurnRepository

SessionFactory = Callable[[], Session]


def negotiation_turn_to_model(turn: NegotiationTurn) -> NegotiationTurnModel:
    return NegotiationTurnModel(
        id=turn.id,
        session_id=turn.session_id,
        speaker=turn.speaker.value,
        content=turn.content,
        turn_number=turn.turn_number,
        created_at=turn.created_at,
    )


def negotiation_turn_to_domain(model: NegotiationTurnModel) -> NegotiationTurn:
    return NegotiationTurn(
        id=model.id,
        session_id=model.session_id,
        speaker=NegotiationTurnSpeaker(model.speaker),
        content=model.content,
        turn_number=model.turn_number,
        created_at=model.created_at,
    )


class SQLNegotiationTurnRepository(NegotiationTurnRepository):
    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    def create(self, turn: NegotiationTurn, user_id: UUID) -> NegotiationTurn:
        with self._session_factory() as database_session:
            session_exists = database_session.scalar(
                select(NegotiationSessionModel.id).where(
                    NegotiationSessionModel.id == turn.session_id,
                    NegotiationSessionModel.user_id == user_id,
                )
            )
            if session_exists is None:
                raise NegotiationSessionNotFoundError(turn.session_id)
            model = negotiation_turn_to_model(turn)
            database_session.add(model)
            try:
                database_session.commit()
                database_session.refresh(model)
            except SQLAlchemyError:
                database_session.rollback()
                raise

            return negotiation_turn_to_domain(model)

    def get_for_user(self, turn_id: UUID, user_id: UUID) -> NegotiationTurn | None:
        with self._session_factory() as database_session:
            model = database_session.scalar(
                select(NegotiationTurnModel)
                .join(
                    NegotiationSessionModel,
                    NegotiationSessionModel.id == NegotiationTurnModel.session_id,
                )
                .where(
                    NegotiationTurnModel.id == turn_id,
                    NegotiationSessionModel.user_id == user_id,
                )
            )
            return None if model is None else negotiation_turn_to_domain(model)

    def list_by_session_for_user(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> list[NegotiationTurn]:
        with self._session_factory() as database_session:
            models = database_session.scalars(
                select(NegotiationTurnModel)
                .join(
                    NegotiationSessionModel,
                    NegotiationSessionModel.id == NegotiationTurnModel.session_id,
                )
                .where(
                    NegotiationTurnModel.session_id == session_id,
                    NegotiationSessionModel.user_id == user_id,
                )
                .order_by(NegotiationTurnModel.turn_number)
            ).all()
            return [negotiation_turn_to_domain(model) for model in models]
