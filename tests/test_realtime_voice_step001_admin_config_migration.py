# -*- coding: utf-8 -*-
"""实时语音 M1 / STEP-001：admin配置草稿修订号迁移。"""

from __future__ import annotations

import importlib.util
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.util.exc import CommandError
from sqlalchemy import Integer

from backend.config import get_mysql_sync_migration_url
from backend.models.admin_config import AdminConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    PROJECT_ROOT / "alembic/versions/v8a_voice_admin_config_draft_revision.py"
)
REVISION = "v8a_voice_draft_rev_001"
DOWN_REVISION = "v7a_admin_token_ver_001"
INTEGRATION_DATABASE_ENV = "REALTIME_VOICE_STEP001_DATABASE"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "realtime_voice_step001_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_admin_config_draft_revision_model_contract():
    column = AdminConfig.__table__.columns["draft_revision"]

    assert isinstance(column.type, Integer)
    assert column.nullable is True
    assert column.default is None
    assert column.server_default is None
    assert column.index is None
    assert column.unique is None


def test_migration_adds_only_nullable_integer_column(monkeypatch):
    migration = _load_migration()
    fake_op = Mock()
    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()

    assert migration.revision == REVISION
    assert migration.down_revision == DOWN_REVISION
    fake_op.add_column.assert_called_once()
    table_name, column = fake_op.add_column.call_args.args
    assert table_name == "admin_config"
    assert column.name == "draft_revision"
    assert isinstance(column.type, Integer)
    assert column.nullable is True
    assert column.default is None
    assert column.server_default is None
    assert len(fake_op.method_calls) == 1


def test_migration_downgrade_drops_only_draft_revision(monkeypatch):
    migration = _load_migration()
    fake_op = Mock()
    monkeypatch.setattr(migration, "op", fake_op)

    migration.downgrade()

    fake_op.drop_column.assert_called_once_with("admin_config", "draft_revision")
    assert len(fake_op.method_calls) == 1


def _baseline_admin_config(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "admin_config",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("config_key", sa.String(100), nullable=False, index=True),
        sa.Column("config_value", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_draft", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.String(50), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def _current_revision(engine: sa.Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _project_rows(
    engine: sa.Engine,
    table: sa.Table,
    existing_columns: list[str],
) -> Counter[tuple[object, ...]]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(*(table.c[name] for name in existing_columns)).order_by(table.c.id)
        ).all()
    return Counter(tuple(row) for row in rows)


@pytest.mark.skipif(
    not os.getenv(INTEGRATION_DATABASE_ENV),
    reason=f"需要设置隔离 MySQL 库名 {INTEGRATION_DATABASE_ENV}",
)
def test_mysql_upgrade_repeat_downgrade_preserves_existing_projection(
    monkeypatch: pytest.MonkeyPatch,
):
    database_name = os.environ[INTEGRATION_DATABASE_ENV]
    assert database_name.startswith("lxm_step001_"), "只允许使用 STEP-001 隔离测试库"
    metadata = sa.MetaData()
    admin_config = _baseline_admin_config(metadata)
    rows = [
        {
            "id": 101,
            "config_key": "voice_call_config",
            "config_value": '{"enabled":false,"label":"旧值"}',
            "version": 3,
            "is_active": True,
            "is_draft": False,
            "updated_by": "admin_a",
            "updated_at": datetime(2026, 8, 30, 1, 2, 3),
        },
        {
            "id": 102,
            "config_key": "voice_call_config",
            "config_value": None,
            "version": 0,
            "is_active": False,
            "is_draft": True,
            "updated_by": None,
            "updated_at": datetime(2026, 8, 30, 4, 5, 6),
        },
        {
            "id": 103,
            "config_key": "voice_call_config",
            "config_value": "",
            "version": 2,
            "is_active": False,
            "is_draft": False,
            "updated_by": "历史管理员",
            "updated_at": datetime(2026, 8, 30, 7, 8, 9),
        },
        {
            "id": 104,
            "config_key": "persona",
            "config_value": '{"content":"' + ("多字节旧正文" * 512) + '"}',
            "version": 20,
            "is_active": True,
            "is_draft": False,
            "updated_by": "admin_b",
            "updated_at": datetime(2026, 8, 30, 10, 11, 12),
        },
    ]
    existing_columns = [column.name for column in admin_config.columns]
    monkeypatch.setenv("MYSQL_DATABASE", database_name)

    engine = sa.create_engine(get_mysql_sync_migration_url(), poolclass=sa.pool.NullPool)
    inspector = sa.inspect(engine)
    assert inspector.get_table_names() == [], "隔离测试库必须为空库"
    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))

    try:
        metadata.create_all(engine)
        with engine.connect() as connection:
            mysql_version = connection.execute(sa.text("SELECT VERSION()")).scalar_one()
        assert str(mysql_version).startswith("8.")
        with engine.begin() as connection:
            connection.execute(admin_config.insert(), rows)
        before_projection = _project_rows(engine, admin_config, existing_columns)

        command.stamp(alembic_config, DOWN_REVISION)
        assert _current_revision(engine) == DOWN_REVISION

        command.upgrade(alembic_config, REVISION)
        assert _current_revision(engine) == REVISION
        upgraded_columns = {
            column["name"]: column for column in sa.inspect(engine).get_columns("admin_config")
        }
        assert set(upgraded_columns) == {*existing_columns, "draft_revision"}
        assert upgraded_columns["draft_revision"]["nullable"] is True
        assert isinstance(upgraded_columns["draft_revision"]["type"], Integer)
        assert _project_rows(engine, admin_config, existing_columns) == before_projection
        with engine.connect() as connection:
            assert connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM admin_config "
                    "WHERE draft_revision IS NOT NULL"
                )
            ).scalar_one() == 0

        # Alembic 在已处于目标 revision 时不得再次执行 ADD COLUMN。
        command.upgrade(alembic_config, REVISION)
        assert _current_revision(engine) == REVISION
        assert _project_rows(engine, admin_config, existing_columns) == before_projection

        # 物理列与 revision 状态发生漂移时，严格 ALTER 必须报重复列，不能静默跳过。
        command.stamp(alembic_config, DOWN_REVISION)
        with pytest.raises(sa.exc.OperationalError) as duplicate_column_error:
            command.upgrade(alembic_config, REVISION)
        assert duplicate_column_error.value.orig.args[0] == 1060
        assert _current_revision(engine) == DOWN_REVISION
        command.stamp(alembic_config, REVISION)

        # 链状态损坏必须显式失败，不能把未知 revision 静默当成已完成。
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE alembic_version SET version_num = "
                    "'missing_realtime_voice_revision'"
                )
            )
        with pytest.raises(CommandError):
            command.upgrade(alembic_config, REVISION)
        with engine.begin() as connection:
            connection.execute(
                sa.text("UPDATE alembic_version SET version_num = :revision"),
                {"revision": REVISION},
            )

        command.downgrade(alembic_config, DOWN_REVISION)
        assert _current_revision(engine) == DOWN_REVISION
        downgraded_columns = {
            column["name"] for column in sa.inspect(engine).get_columns("admin_config")
        }
        assert downgraded_columns == set(existing_columns)
        assert _project_rows(engine, admin_config, existing_columns) == before_projection
    finally:
        alembic_version = sa.Table("alembic_version", sa.MetaData())
        alembic_version.drop(engine, checkfirst=True)
        admin_config.drop(engine, checkfirst=True)
        engine.dispose()
