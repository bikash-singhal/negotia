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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class NegotiationDebriefModel(Base):
    __tablename__ = "negotiation_debriefs"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            name="uq_negotiation_debriefs_session_id",
        ),
        CheckConstraint(
            "observation_count > 0",
            name="ck_negotiation_debriefs_observation_count_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiation_sessions.id",
            name="fk_negotiation_debriefs_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    repeated_strengths: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    repeated_weaknesses: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    key_missed_opportunities: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    recurring_risks: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    overall_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
