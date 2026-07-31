from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class NegotiationSessionModel(Base):
    __tablename__ = "negotiation_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'active', 'completed', 'abandoned')",
            name="ck_negotiation_sessions_status",
        ),
        Index(
            "ix_negotiation_sessions_scenario_id",
            "scenario_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    scenario_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "scenarios.scenario_id",
            name="fk_negotiation_sessions_scenario_id_scenarios",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
