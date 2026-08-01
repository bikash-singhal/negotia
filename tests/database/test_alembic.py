from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from app.database.base import Base

PROJECT_ROOT = Path(__file__).parents[2]
INITIAL_REVISION_ID = "080962b433df"
USER_REVISION_ID = "e13a7d9c4b62"
OWNERSHIP_REVISION_ID = "b5f2c8a91d43"
MEMORY_V2_REVISION_ID = "c4d8e2f7a1b3"
EXPECTED_TABLE_ORDER = (
    "scenarios",
    "negotiation_sessions",
    "negotiation_turns",
    "coach_observations",
    "negotiation_debriefs",
    "negotiation_strategies",
    "negotiator_memories",
    "negotiator_memory_sources",
    "users",
)


def _alembic_config() -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"))


def test_alembic_config_has_linear_revision_history_and_no_duplicate_url() -> None:
    config = _alembic_config()
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()

    assert config.get_main_option("sqlalchemy.url") is None
    assert head == MEMORY_V2_REVISION_ID

    memory_v2_revision = scripts.get_revision(head)
    assert memory_v2_revision is not None
    assert memory_v2_revision.down_revision == OWNERSHIP_REVISION_ID
    assert memory_v2_revision.doc == "memory_v2"

    ownership_revision = scripts.get_revision(OWNERSHIP_REVISION_ID)
    assert ownership_revision is not None
    assert ownership_revision.down_revision == USER_REVISION_ID
    assert ownership_revision.doc == "add_resource_ownership"

    user_revision = scripts.get_revision(USER_REVISION_ID)
    assert user_revision is not None
    assert user_revision.down_revision == INITIAL_REVISION_ID
    assert user_revision.doc == "add_users"

    initial_revision = scripts.get_revision(INITIAL_REVISION_ID)
    assert initial_revision is not None
    assert initial_revision.down_revision is None
    assert initial_revision.doc == "create_initial_schema"


def test_offline_upgrade_compiles_all_tables_in_dependency_order(
    capsys: pytest.CaptureFixture[str],
) -> None:
    command.upgrade(_alembic_config(), "head", sql=True)
    captured = capsys.readouterr()
    sql = captured.out

    positions = [
        sql.index(f"CREATE TABLE {table_name}") for table_name in EXPECTED_TABLE_ORDER
    ]
    assert positions == sorted(positions)
    assert "CREATE TABLE alembic_version" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "JSONB NOT NULL" in sql

    expected_schema_object_names = {
        schema_object.name
        for table in Base.metadata.tables.values()
        for schema_object in (*table.constraints, *table.indexes)
        if isinstance(schema_object.name, str)
    }
    for schema_object_name in expected_schema_object_names:
        assert schema_object_name in sql


def test_offline_downgrade_drops_tables_in_reverse_dependency_order(
    capsys: pytest.CaptureFixture[str],
) -> None:
    command.downgrade(_alembic_config(), f"{MEMORY_V2_REVISION_ID}:base", sql=True)
    captured = capsys.readouterr()
    sql = captured.out

    positions = [
        sql.index(f"DROP TABLE {table_name}")
        for table_name in reversed(EXPECTED_TABLE_ORDER)
    ]
    assert positions == sorted(positions)


def test_memory_v2_migration_clears_only_incompatible_memory_records(
    capsys: pytest.CaptureFixture[str],
) -> None:
    command.upgrade(
        _alembic_config(),
        f"{OWNERSHIP_REVISION_ID}:{MEMORY_V2_REVISION_ID}",
        sql=True,
    )
    captured = capsys.readouterr()
    sql = captured.out

    assert "DELETE FROM negotiator_memory_sources" in sql
    assert "DELETE FROM negotiator_memories" in sql
    assert "DELETE FROM users" not in sql
    assert "TRUNCATE TABLE scenarios" not in sql
    assert "stable_strengths" in sql
    assert "highest_priority_skill" in sql
