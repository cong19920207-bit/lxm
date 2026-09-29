# -*- coding: utf-8 -*-
"""实时语音 M1 / STEP-002：成长记录来源幂等迁移。"""

from __future__ import annotations

import importlib.util
import os
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, call

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Date, Integer, String

from backend.config import get_mysql_sync_migration_url
from backend.models.relationship_growth_log import RelationshipGrowthLog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "alembic/versions/v8b_voice_relationship_growth_source.py"
)
REVISION = "v8b_voice_growth_src_001"
DOWN_REVISION = "v8a_voice_draft_rev_001"
INTEGRATION_DATABASE_ENV = "REALTIME_VOICE_STEP002_DATABASE"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "realtime_voice_step002_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_relationship_growth_log_model_contract():
    table = RelationshipGrowthLog.__table__

    expected = {
        "source_type": (String, 64),
        "source_id": (String, 64),
        "eligible_seconds": (Integer, None),
        "business_date": (Date, None),
    }
    for name, (type_class, length) in expected.items():
        column = table.columns[name]
        assert isinstance(column.type, type_class)
        if length is not None:
            assert column.type.length == length
        assert column.nullable is True
        assert column.default is None
        assert column.server_default is None

    unique_indexes = {
        index.name: (tuple(column.name for column in index.columns), index.unique)
        for index in table.indexes
        if index.unique
    }
    assert unique_indexes == {
        "uk_growth_source": (("source_type", "source_id"), True),
    }


def test_legacy_growth_log_constructor_keeps_new_fields_null():
    row = RelationshipGrowthLog(
        user_id=7,
        action_type="dialog",
        points=2,
        created_at=datetime(2026, 8, 31, 1, 2, 3),
    )

    assert row.source_type is None
    assert row.source_id is None
    assert row.eligible_seconds is None
    assert row.business_date is None


def test_migration_upgrade_adds_only_four_nullable_columns_and_unique_index(
    monkeypatch: pytest.MonkeyPatch,
):
    migration = _load_migration()
    fake_op = Mock()
    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()

    assert migration.revision == REVISION
    assert migration.down_revision == DOWN_REVISION
    assert [call.args[1].name for call in fake_op.add_column.call_args_list] == [
        "source_type",
        "source_id",
        "eligible_seconds",
        "business_date",
    ]
    for call in fake_op.add_column.call_args_list:
        table_name, column = call.args
        assert table_name == "relationship_growth_log"
        assert column.nullable is True
        assert column.default is None
        assert column.server_default is None
    fake_op.create_index.assert_called_once_with(
        "uk_growth_source",
        "relationship_growth_log",
        ["source_type", "source_id"],
        unique=True,
    )
    assert len(fake_op.method_calls) == 5


def test_migration_downgrade_removes_only_index_and_four_columns(
    monkeypatch: pytest.MonkeyPatch,
):
    migration = _load_migration()
    fake_op = Mock()
    monkeypatch.setattr(migration, "op", fake_op)

    migration.downgrade()

    assert fake_op.method_calls == [
        call.drop_index(
            "uk_growth_source", table_name="relationship_growth_log"
        ),
        call.drop_column(
            "relationship_growth_log", "business_date"
        ),
        call.drop_column(
            "relationship_growth_log", "eligible_seconds"
        ),
        call.drop_column(
            "relationship_growth_log", "source_id"
        ),
        call.drop_column(
            "relationship_growth_log", "source_type"
        ),
    ]


def _baseline_tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table]:
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    )
    growth = sa.Table(
        "relationship_growth_log",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    return users, growth


def _current_revision(engine: sa.Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _project_rows(
    engine: sa.Engine,
    table: sa.Table,
    columns: list[str],
) -> Counter[tuple[object, ...]]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(*(table.c[name] for name in columns)).order_by(table.c.id)
        ).all()
    return Counter(tuple(row) for row in rows)


@pytest.mark.skipif(
    not os.getenv(INTEGRATION_DATABASE_ENV),
    reason=f"需要设置隔离 MySQL 库名 {INTEGRATION_DATABASE_ENV}",
)
def test_mysql8_upgrade_null_unique_semantics_and_downgrade_preserve_projection(
    monkeypatch: pytest.MonkeyPatch,
):
    database_name = os.environ[INTEGRATION_DATABASE_ENV]
    assert database_name.startswith("lxm_step002_"), "只允许使用 STEP-002 隔离测试库"
    monkeypatch.setenv("MYSQL_DATABASE", database_name)

    metadata = sa.MetaData()
    users, growth = _baseline_tables(metadata)
    existing_columns = [column.name for column in growth.columns]
    engine = sa.create_engine(get_mysql_sync_migration_url(), poolclass=sa.pool.NullPool)
    assert sa.inspect(engine).get_table_names() == [], "隔离测试库必须为空库"
    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))

    baseline_rows = [
        {
            "id": 101,
            "user_id": 1,
            "action_type": "dialog",
            "points": 2,
            "created_at": datetime(2026, 8, 30, 1, 2, 3),
        },
        {
            "id": 102,
            "user_id": 1,
            "action_type": "daily_login",
            "points": 5,
            "created_at": datetime(2026, 8, 30, 4, 5, 6),
        },
    ]

    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            mysql_version = connection.execute(sa.text("SELECT VERSION()"))
            assert str(mysql_version.scalar_one()).startswith("8.")
            connection.execute(users.insert(), {"id": 1})
            connection.execute(growth.insert(), baseline_rows)
        before_upgrade = _project_rows(engine, growth, existing_columns)

        command.stamp(alembic_config, DOWN_REVISION)
        assert _current_revision(engine) == DOWN_REVISION
        command.upgrade(alembic_config, REVISION)
        assert _current_revision(engine) == REVISION

        inspector = sa.inspect(engine)
        upgraded_columns = {
            column["name"]: column
            for column in inspector.get_columns("relationship_growth_log")
        }
        assert set(upgraded_columns) == {
            *existing_columns,
            "source_type",
            "source_id",
            "eligible_seconds",
            "business_date",
        }
        for name in ("source_type", "source_id", "eligible_seconds", "business_date"):
            assert upgraded_columns[name]["nullable"] is True
        unique_indexes = {
            index["name"]: (tuple(index["column_names"]), index["unique"])
            for index in inspector.get_indexes("relationship_growth_log")
            if index["unique"]
        }
        assert unique_indexes == {
            "uk_growth_source": (("source_type", "source_id"), True),
        }
        assert _project_rows(engine, growth, existing_columns) == before_upgrade
        with engine.connect() as connection:
            null_rows = connection.execute(
                sa.text(
                    "SELECT id, source_type, source_id, eligible_seconds, business_date "
                    "FROM relationship_growth_log ORDER BY id"
                )
            ).all()
        assert null_rows == [(101, None, None, None, None), (102, None, None, None, None)]

        reflected = sa.Table(
            "relationship_growth_log",
            sa.MetaData(),
            autoload_with=engine,
        )
        # MySQL 8 的复合 UNIQUE 只在两个组成列都非 NULL 时去重。
        with engine.begin() as connection:
            connection.execute(
                reflected.insert(),
                [
                    {
                        "user_id": 1,
                        "action_type": "dialog",
                        "points": 2,
                        "source_type": None,
                        "source_id": None,
                        "eligible_seconds": None,
                        "business_date": None,
                        "created_at": datetime(2026, 8, 30, 7, 8, 9),
                    },
                    {
                        "user_id": 1,
                        "action_type": "dialog",
                        "points": 2,
                        "source_type": None,
                        "source_id": None,
                        "eligible_seconds": None,
                        "business_date": None,
                        "created_at": datetime(2026, 8, 30, 10, 11, 12),
                    },
                    {
                        "user_id": 1,
                        "action_type": "voice_call",
                        "points": 10,
                        "source_type": "voice_call",
                        "source_id": "call-step002-001",
                        "eligible_seconds": 65,
                        "business_date": date(2026, 8, 31),
                        "created_at": datetime(2026, 8, 31, 1, 2, 3),
                    },
                ],
            )
        with pytest.raises(sa.exc.IntegrityError) as duplicate_source:
            with engine.begin() as connection:
                connection.execute(
                    reflected.insert(),
                    {
                        "user_id": 1,
                        "action_type": "voice_call",
                        "points": 10,
                        "source_type": "voice_call",
                        "source_id": "call-step002-001",
                        "eligible_seconds": 65,
                        "business_date": date(2026, 8, 31),
                        "created_at": datetime(2026, 8, 31, 1, 2, 4),
                    },
                )
        assert duplicate_source.value.orig.args[0] == 1062

        # 已在目标 revision 时再次 upgrade 是 Alembic no-op，不重复 ALTER。
        command.upgrade(alembic_config, REVISION)
        assert _current_revision(engine) == REVISION

        before_downgrade = _project_rows(engine, growth, existing_columns)
        command.downgrade(alembic_config, DOWN_REVISION)
        assert _current_revision(engine) == DOWN_REVISION
        downgraded_inspector = sa.inspect(engine)
        assert {
            column["name"]
            for column in downgraded_inspector.get_columns("relationship_growth_log")
        } == set(existing_columns)
        assert "uk_growth_source" not in {
            index["name"]
            for index in downgraded_inspector.get_indexes("relationship_growth_log")
        }
        assert _project_rows(engine, growth, existing_columns) == before_downgrade
    finally:
        alembic_version = sa.Table("alembic_version", sa.MetaData())
        alembic_version.drop(engine, checkfirst=True)
        growth.drop(engine, checkfirst=True)
        users.drop(engine, checkfirst=True)
        engine.dispose()
