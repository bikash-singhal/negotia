from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CoachObservationModel(Base):
    __tablename__ = "coach_observations"
    __table_args__ = (
        UniqueConstraint(
            "user_turn_id",
            "opponent_turn_id",
            name="uq_coach_observations_user_turn_id_opponent_turn_id",
        ),
        Index(
            "ix_coach_observations_session_id_created_at_id",
            "session_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiation_sessions.id",
            name="fk_coach_observations_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    user_turn_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiation_turns.id",
            name="fk_coach_observations_user_turn_id_negotiation_turns",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    opponent_turn_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiation_turns.id",
            name="fk_coach_observations_opponent_turn_id_negotiation_turns",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    strengths: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    weaknesses: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    missed_opportunities: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    risk_signals: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
