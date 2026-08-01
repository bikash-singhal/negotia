from collections.abc import Iterable

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.database import models
from app.database.base import Base

EXPECTED_TABLES = {
    "coach_observations",
    "negotiation_debriefs",
    "negotiation_sessions",
    "negotiation_strategies",
    "negotiation_turns",
    "negotiator_memories",
    "negotiator_memory_sources",
    "scenarios",
    "users",
}


def _constraint_names(
    table_name: str,
    constraint_type: type[CheckConstraint] | type[UniqueConstraint],
) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type) and isinstance(constraint.name, str)
    }


def _unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _assert_jsonb_columns(table_name: str, column_names: Iterable[str]) -> None:
    table = Base.metadata.tables[table_name]
    for column_name in column_names:
        assert isinstance(table.c[column_name].type, JSONB)


def test_importing_models_registers_all_expected_tables() -> None:
    assert models.ScenarioModel.__table__ is Base.metadata.tables["scenarios"]
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_primary_keys_match_domain_identifiers() -> None:
    expected_primary_keys = {
        "scenarios": ("scenario_id",),
        "negotiation_sessions": ("id",),
        "negotiation_turns": ("id",),
        "coach_observations": ("id",),
        "negotiation_debriefs": ("id",),
        "negotiation_strategies": ("id",),
        "negotiator_memories": ("id",),
        "negotiator_memory_sources": ("memory_id", "session_id"),
        "users": ("id",),
    }

    for table_name, expected_columns in expected_primary_keys.items():
        table = Base.metadata.tables[table_name]
        assert tuple(table.primary_key.columns.keys()) == expected_columns
        for column in table.primary_key.columns:
            assert isinstance(column.type, PGUUID)
            assert column.type.as_uuid is True


def test_foreign_keys_reference_expected_parent_tables() -> None:
    expected_foreign_keys = {
        "scenarios": {
            ("user_id", "users.id"),
        },
        "negotiation_sessions": {
            ("scenario_id", "scenarios.scenario_id"),
            ("user_id", "users.id"),
        },
        "negotiation_turns": {
            ("session_id", "negotiation_sessions.id"),
        },
        "coach_observations": {
            ("session_id", "negotiation_sessions.id"),
            ("user_turn_id", "negotiation_turns.id"),
            ("opponent_turn_id", "negotiation_turns.id"),
        },
        "negotiation_debriefs": {
            ("session_id", "negotiation_sessions.id"),
        },
        "negotiation_strategies": {
            ("session_id", "negotiation_sessions.id"),
            ("debrief_id", "negotiation_debriefs.id"),
        },
        "negotiator_memories": {
            ("trigger_session_id", "negotiation_sessions.id"),
            ("user_id", "users.id"),
        },
        "negotiator_memory_sources": {
            ("memory_id", "negotiator_memories.id"),
            ("session_id", "negotiation_sessions.id"),
        },
    }

    for table_name, expected in expected_foreign_keys.items():
        table = Base.metadata.tables[table_name]
        actual = {
            (foreign_key.parent.name, foreign_key.target_fullname)
            for foreign_key in table.foreign_keys
        }
        assert actual == expected
        assert all(
            foreign_key.ondelete == "RESTRICT" for foreign_key in table.foreign_keys
        )


def test_check_constraints_encode_domain_values_and_positive_counts() -> None:
    expected_names = {
        "scenarios": {"ck_scenarios_difficulty"},
        "negotiation_sessions": {"ck_negotiation_sessions_status"},
        "negotiation_turns": {
            "ck_negotiation_turns_speaker",
            "ck_negotiation_turns_turn_number_positive",
        },
        "negotiation_debriefs": {
            "ck_negotiation_debriefs_observation_count_positive",
        },
        "negotiator_memories": {
            "ck_negotiator_memories_sessions_analyzed_positive",
        },
        "negotiator_memory_sources": {
            "ck_negotiator_memory_sources_source_order_nonnegative",
        },
    }

    for table_name, expected in expected_names.items():
        assert _constraint_names(table_name, CheckConstraint) == expected


def test_unique_constraints_preserve_repository_invariants() -> None:
    assert _unique_column_sets("negotiation_turns") == {
        ("session_id", "turn_number"),
    }
    assert _unique_column_sets("coach_observations") == {
        ("user_turn_id", "opponent_turn_id"),
    }
    assert _unique_column_sets("negotiation_debriefs") == {("session_id",)}
    assert _unique_column_sets("negotiation_strategies") == {("session_id",)}
    assert _unique_column_sets("negotiator_memories") == {
        ("trigger_session_id",),
    }
    assert _unique_column_sets("negotiator_memory_sources") == {
        ("memory_id", "source_order"),
    }
    assert _unique_column_sets("users") == {("username",)}


def test_generated_and_list_fields_use_jsonb() -> None:
    _assert_jsonb_columns(
        "scenarios",
        ("constraints", "hidden_context", "walk_away_conditions"),
    )
    _assert_jsonb_columns(
        "coach_observations",
        ("strengths", "weaknesses", "missed_opportunities", "risk_signals"),
    )
    _assert_jsonb_columns(
        "negotiation_debriefs",
        (
            "repeated_strengths",
            "repeated_weaknesses",
            "key_missed_opportunities",
            "recurring_risks",
        ),
    )
    _assert_jsonb_columns(
        "negotiation_strategies",
        (
            "prioritized_tactics",
            "long_term_skills",
            "preparation_checklist",
            "avoid_next_time",
        ),
    )
    _assert_jsonb_columns(
        "negotiator_memories",
        (
            "recurring_strengths",
            "recurring_weaknesses",
            "improving_skills",
            "persistent_risks",
            "priority_focus_areas",
            "recommended_drills",
        ),
    )


def test_all_datetime_columns_are_timezone_aware() -> None:
    datetime_columns = {
        "scenarios": ("created_at", "updated_at"),
        "negotiation_sessions": ("created_at", "updated_at"),
        "negotiation_turns": ("created_at",),
        "coach_observations": ("created_at",),
        "negotiation_debriefs": ("created_at",),
        "negotiation_strategies": ("created_at",),
        "negotiator_memories": ("created_at",),
        "users": ("created_at",),
    }

    for table_name, column_names in datetime_columns.items():
        table = Base.metadata.tables[table_name]
        for column_name in column_names:
            assert table.c[column_name].type.timezone is True


def test_memory_trigger_nullability_and_indexes_support_repository_queries() -> None:
    memory_table = Base.metadata.tables["negotiator_memories"]
    assert memory_table.c.trigger_session_id.nullable is True
    assert {
        index.name: tuple(column.name for column in index.columns)
        for index in memory_table.indexes
    } == {
        "ix_negotiator_memories_created_at_id": ("created_at", "id"),
        "ix_negotiator_memories_user_id_created_at_id": (
            "user_id",
            "created_at",
            "id",
        ),
    }

    turn_table = Base.metadata.tables["negotiation_turns"]
    turn_number_constraint = next(
        constraint
        for constraint in turn_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_negotiation_turns_session_id_turn_number"
    )
    assert tuple(turn_number_constraint.columns.keys()) == (
        "session_id",
        "turn_number",
    )


def test_scenario_jsonb_defaults_are_independent_callable_factories() -> None:
    scenario_table = Base.metadata.tables["scenarios"]
    for column_name in ("constraints", "hidden_context", "walk_away_conditions"):
        default = scenario_table.c[column_name].default
        assert default is not None
        assert default.is_callable
