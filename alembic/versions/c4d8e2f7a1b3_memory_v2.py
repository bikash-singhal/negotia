"""memory_v2

Revision ID: c4d8e2f7a1b3
Revises: b5f2c8a91d43
Create Date: 2026-08-01 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4d8e2f7a1b3"
down_revision: str | Sequence[str] | None = "b5f2c8a91d43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace pre-release Memory records with the compact V2 schema."""
    op.execute("DELETE FROM negotiator_memory_sources")
    op.execute("DELETE FROM negotiator_memories")

    op.alter_column(
        "negotiator_memories",
        "recurring_strengths",
        new_column_name="stable_strengths",
    )
    op.alter_column(
        "negotiator_memories",
        "recurring_weaknesses",
        new_column_name="stable_weaknesses",
    )
    op.drop_column("negotiator_memories", "priority_focus_areas")
    op.drop_column("negotiator_memories", "recommended_drills")
    op.add_column(
        "negotiator_memories",
        sa.Column("highest_priority_skill", sa.Text(), nullable=False),
    )
    op.add_column(
        "negotiator_memories",
        sa.Column("next_session_drill", sa.Text(), nullable=False),
    )
    op.add_column(
        "negotiator_memories",
        sa.Column("progress_summary", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    """Restore the V1 Memory schema without attempting lossy data conversion."""
    op.execute("DELETE FROM negotiator_memory_sources")
    op.execute("DELETE FROM negotiator_memories")

    op.drop_column("negotiator_memories", "progress_summary")
    op.drop_column("negotiator_memories", "next_session_drill")
    op.drop_column("negotiator_memories", "highest_priority_skill")
    op.add_column(
        "negotiator_memories",
        sa.Column(
            "priority_focus_areas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
    )
    op.add_column(
        "negotiator_memories",
        sa.Column(
            "recommended_drills",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
    )
    op.alter_column(
        "negotiator_memories",
        "stable_weaknesses",
        new_column_name="recurring_weaknesses",
    )
    op.alter_column(
        "negotiator_memories",
        "stable_strengths",
        new_column_name="recurring_strengths",
    )
