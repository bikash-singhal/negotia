from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class NegotiationStrategyModel(Base):
    __tablename__ = "negotiation_strategies"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            name="uq_negotiation_strategies_session_id",
        ),
        Index(
            "ix_negotiation_strategies_debrief_id",
            "debrief_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiation_sessions.id",
            name="fk_negotiation_strategies_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    debrief_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiation_debriefs.id",
            name="fk_negotiation_strategies_debrief_id_negotiation_debriefs",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    primary_objective: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    prioritized_tactics: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    long_term_skills: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    preparation_checklist: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    avoid_next_time: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
