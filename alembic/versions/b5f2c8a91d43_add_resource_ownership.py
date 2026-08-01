"""add_resource_ownership

Revision ID: b5f2c8a91d43
Revises: e13a7d9c4b62
Create Date: 2026-08-01 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b5f2c8a91d43"
down_revision: str | Sequence[str] | None = "e13a7d9c4b62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Delete unowned pre-release data and add user ownership."""
    op.execute("TRUNCATE TABLE scenarios CASCADE")

    op.add_column(
        "scenarios",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_scenarios_user_id_users",
        "scenarios",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_scenarios_user_id_created_at_scenario_id",
        "scenarios",
        ["user_id", "created_at", "scenario_id"],
        unique=False,
    )

    op.add_column(
        "negotiation_sessions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_negotiation_sessions_user_id_users",
        "negotiation_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_negotiation_sessions_user_id_created_at_id",
        "negotiation_sessions",
        ["user_id", "created_at", "id"],
        unique=False,
    )

    op.add_column(
        "negotiator_memories",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_negotiator_memories_user_id_users",
        "negotiator_memories",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_negotiator_memories_user_id_created_at_id",
        "negotiator_memories",
        ["user_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove user ownership columns."""
    op.drop_index(
        "ix_negotiator_memories_user_id_created_at_id",
        table_name="negotiator_memories",
    )
    op.drop_constraint(
        "fk_negotiator_memories_user_id_users",
        "negotiator_memories",
        type_="foreignkey",
    )
    op.drop_column("negotiator_memories", "user_id")

    op.drop_index(
        "ix_negotiation_sessions_user_id_created_at_id",
        table_name="negotiation_sessions",
    )
    op.drop_constraint(
        "fk_negotiation_sessions_user_id_users",
        "negotiation_sessions",
        type_="foreignkey",
    )
    op.drop_column("negotiation_sessions", "user_id")

    op.drop_index(
        "ix_scenarios_user_id_created_at_scenario_id",
        table_name="scenarios",
    )
    op.drop_constraint(
        "fk_scenarios_user_id_users",
        "scenarios",
        type_="foreignkey",
    )
    op.drop_column("scenarios", "user_id")
