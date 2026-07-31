"""create_initial_schema

Revision ID: 080962b433df
Revises:
Create Date: 2026-07-31 17:06:47.506761

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "080962b433df"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "scenarios",
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("industry", sa.Text(), nullable=False),
        sa.Column("opponent_role", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.Text(), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("negotiation_style", sa.Text(), nullable=False),
        sa.Column("constraints", postgresql.JSONB(), nullable=False),
        sa.Column("hidden_context", postgresql.JSONB(), nullable=False),
        sa.Column("walk_away_conditions", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "difficulty IN ('beginner', 'intermediate', 'advanced')",
            name="ck_scenarios_difficulty",
        ),
        sa.PrimaryKeyConstraint("scenario_id"),
    )

    op.create_table(
        "negotiation_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('created', 'active', 'completed', 'abandoned')",
            name="ck_negotiation_sessions_status",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.scenario_id"],
            name="fk_negotiation_sessions_scenario_id_scenarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_negotiation_sessions_scenario_id",
        "negotiation_sessions",
        ["scenario_id"],
        unique=False,
    )

    op.create_table(
        "negotiation_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "speaker IN ('user', 'opponent')",
            name="ck_negotiation_turns_speaker",
        ),
        sa.CheckConstraint(
            "turn_number > 0",
            name="ck_negotiation_turns_turn_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["negotiation_sessions.id"],
            name="fk_negotiation_turns_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "turn_number",
            name="uq_negotiation_turns_session_id_turn_number",
        ),
    )

    op.create_table(
        "coach_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opponent_turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strengths", postgresql.JSONB(), nullable=False),
        sa.Column("weaknesses", postgresql.JSONB(), nullable=False),
        sa.Column("missed_opportunities", postgresql.JSONB(), nullable=False),
        sa.Column("risk_signals", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["opponent_turn_id"],
            ["negotiation_turns.id"],
            name="fk_coach_observations_opponent_turn_id_negotiation_turns",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["negotiation_sessions.id"],
            name="fk_coach_observations_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_turn_id"],
            ["negotiation_turns.id"],
            name="fk_coach_observations_user_turn_id_negotiation_turns",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_turn_id",
            "opponent_turn_id",
            name="uq_coach_observations_user_turn_id_opponent_turn_id",
        ),
    )
    op.create_index(
        "ix_coach_observations_session_id_created_at_id",
        "coach_observations",
        ["session_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "negotiation_debriefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repeated_strengths", postgresql.JSONB(), nullable=False),
        sa.Column("repeated_weaknesses", postgresql.JSONB(), nullable=False),
        sa.Column("key_missed_opportunities", postgresql.JSONB(), nullable=False),
        sa.Column("recurring_risks", postgresql.JSONB(), nullable=False),
        sa.Column("overall_assessment", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "observation_count > 0",
            name="ck_negotiation_debriefs_observation_count_positive",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["negotiation_sessions.id"],
            name="fk_negotiation_debriefs_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            name="uq_negotiation_debriefs_session_id",
        ),
    )

    op.create_table(
        "negotiation_strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("debrief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_objective", sa.Text(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=False),
        sa.Column("prioritized_tactics", postgresql.JSONB(), nullable=False),
        sa.Column("long_term_skills", postgresql.JSONB(), nullable=False),
        sa.Column("preparation_checklist", postgresql.JSONB(), nullable=False),
        sa.Column("avoid_next_time", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["debrief_id"],
            ["negotiation_debriefs.id"],
            name="fk_negotiation_strategies_debrief_id_negotiation_debriefs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["negotiation_sessions.id"],
            name="fk_negotiation_strategies_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            name="uq_negotiation_strategies_session_id",
        ),
    )
    op.create_index(
        "ix_negotiation_strategies_debrief_id",
        "negotiation_strategies",
        ["debrief_id"],
        unique=False,
    )

    op.create_table(
        "negotiator_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "trigger_session_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("recurring_strengths", postgresql.JSONB(), nullable=False),
        sa.Column("recurring_weaknesses", postgresql.JSONB(), nullable=False),
        sa.Column("improving_skills", postgresql.JSONB(), nullable=False),
        sa.Column("persistent_risks", postgresql.JSONB(), nullable=False),
        sa.Column("priority_focus_areas", postgresql.JSONB(), nullable=False),
        sa.Column("recommended_drills", postgresql.JSONB(), nullable=False),
        sa.Column("sessions_analyzed", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "sessions_analyzed > 0",
            name="ck_negotiator_memories_sessions_analyzed_positive",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_session_id"],
            ["negotiation_sessions.id"],
            name="fk_negotiator_memories_trigger_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trigger_session_id",
            name="uq_negotiator_memories_trigger_session_id",
        ),
    )
    op.create_index(
        "ix_negotiator_memories_created_at_id",
        "negotiator_memories",
        ["created_at", "id"],
        unique=False,
    )

    op.create_table(
        "negotiator_memory_sources",
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "source_order >= 0",
            name="ck_negotiator_memory_sources_source_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"],
            ["negotiator_memories.id"],
            name="fk_negotiator_memory_sources_memory_id_negotiator_memories",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["negotiation_sessions.id"],
            name="fk_negotiator_memory_sources_session_id_negotiation_sessions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "memory_id",
            "session_id",
            name="pk_negotiator_memory_sources",
        ),
        sa.UniqueConstraint(
            "memory_id",
            "source_order",
            name="uq_negotiator_memory_sources_memory_id_source_order",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("negotiator_memory_sources")
    op.drop_index(
        "ix_negotiator_memories_created_at_id",
        table_name="negotiator_memories",
    )
    op.drop_table("negotiator_memories")
    op.drop_index(
        "ix_negotiation_strategies_debrief_id",
        table_name="negotiation_strategies",
    )
    op.drop_table("negotiation_strategies")
    op.drop_table("negotiation_debriefs")
    op.drop_index(
        "ix_coach_observations_session_id_created_at_id",
        table_name="coach_observations",
    )
    op.drop_table("coach_observations")
    op.drop_table("negotiation_turns")
    op.drop_index(
        "ix_negotiation_sessions_scenario_id",
        table_name="negotiation_sessions",
    )
    op.drop_table("negotiation_sessions")
    op.drop_table("scenarios")
