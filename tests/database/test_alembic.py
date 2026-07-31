from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from app.database.base import Base

PROJECT_ROOT = Path(__file__).parents[2]
REVISION_ID = "080962b433df"
EXPECTED_TABLE_ORDER = (
    "scenarios",
    "negotiation_sessions",
    "negotiation_turns",
    "coach_observations",
    "negotiation_debriefs",
    "negotiation_strategies",
    "negotiator_memories",
    "negotiator_memory_sources",
)


def _alembic_config() -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"))


def test_alembic_config_has_one_initial_revision_and_no_duplicate_url() -> None:
    config = _alembic_config()
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()

    assert config.get_main_option("sqlalchemy.url") is None
    assert head == REVISION_ID

    revision = scripts.get_revision(head)
    assert revision is not None
    assert revision.down_revision is None
    assert revision.doc == "create_initial_schema"


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
    command.downgrade(_alembic_config(), f"{REVISION_ID}:base", sql=True)
    captured = capsys.readouterr()
    sql = captured.out

    positions = [
        sql.index(f"DROP TABLE {table_name}")
        for table_name in reversed(EXPECTED_TABLE_ORDER)
    ]
    assert positions == sorted(positions)
