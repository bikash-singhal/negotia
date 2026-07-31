from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class NegotiationTurnModel(Base):
    __tablename__ = "negotiation_turns"
    __table_args__ = (
        CheckConstraint(
            "speaker IN ('user', 'opponent')",
            name="ck_negotiation_turns_speaker",
        ),
        CheckConstraint(
            "turn_number > 0",
            name="ck_negotiation_turns_turn_number_positive",
        ),
        UniqueConstraint(
            "session_id",
            "turn_number",
            name="uq_negotiation_turns_session_id_turn_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiation_sessions.id",
            name="fk_negotiation_turns_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
