from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.negotiation_turn import NegotiationTurnModel
from app.database.session import SessionLocal
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

    def create(self, turn: NegotiationTurn) -> NegotiationTurn:
        with self._session_factory() as database_session:
            model = negotiation_turn_to_model(turn)
            database_session.add(model)
            try:
                database_session.commit()
                database_session.refresh(model)
            except SQLAlchemyError:
                database_session.rollback()
                raise

            return negotiation_turn_to_domain(model)

    def get(self, turn_id: UUID) -> NegotiationTurn | None:
        with self._session_factory() as database_session:
            model = database_session.get(NegotiationTurnModel, turn_id)
            return None if model is None else negotiation_turn_to_domain(model)

    def list_by_session(self, session_id: UUID) -> list[NegotiationTurn]:
        with self._session_factory() as database_session:
            models = database_session.scalars(
                select(NegotiationTurnModel)
                .where(NegotiationTurnModel.session_id == session_id)
                .order_by(NegotiationTurnModel.turn_number)
            ).all()
            return [negotiation_turn_to_domain(model) for model in models]
