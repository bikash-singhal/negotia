from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class NegotiatorMemoryModel(Base):
    __tablename__ = "negotiator_memories"
    __table_args__ = (
        UniqueConstraint(
            "trigger_session_id",
            name="uq_negotiator_memories_trigger_session_id",
        ),
        CheckConstraint(
            "sessions_analyzed > 0",
            name="ck_negotiator_memories_sessions_analyzed_positive",
        ),
        Index(
            "ix_negotiator_memories_created_at_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_negotiator_memories_user_id_created_at_id",
            "user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_negotiator_memories_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    trigger_session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiation_sessions.id",
            name="fk_negotiator_memories_trigger_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    recurring_strengths: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    recurring_weaknesses: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    improving_skills: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    persistent_risks: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    priority_focus_areas: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    recommended_drills: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    sessions_analyzed: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class NegotiatorMemorySourceModel(Base):
    __tablename__ = "negotiator_memory_sources"
    __table_args__ = (
        PrimaryKeyConstraint(
            "memory_id",
            "session_id",
            name="pk_negotiator_memory_sources",
        ),
        UniqueConstraint(
            "memory_id",
            "source_order",
            name="uq_negotiator_memory_sources_memory_id_source_order",
        ),
        CheckConstraint(
            "source_order >= 0",
            name="ck_negotiator_memory_sources_source_order_nonnegative",
        ),
    )

    memory_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiator_memories.id",
            name="fk_negotiator_memory_sources_memory_id_negotiator_memories",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "negotiation_sessions.id",
            name="fk_negotiator_memory_sources_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    source_order: Mapped[int] = mapped_column(Integer, nullable=False)
