# -*- coding: utf-8 -*-
"""STEP-002: admin_users.token_version ORM 与 Alembic 迁移定义。"""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

from sqlalchemy import Integer

from backend.models.admin_user import AdminUser


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/v7a_admin_user_token_version.py"
    )
    spec = importlib.util.spec_from_file_location("step002_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_admin_user_token_version_model_contract():
    column = AdminUser.__table__.columns["token_version"]

    assert isinstance(column.type, Integer)
    assert column.nullable is False
    assert column.default is not None
    assert column.default.arg == 0
    assert column.server_default is not None
    assert str(column.server_default.arg) == "0"


def test_migration_adds_non_null_default_zero_column(monkeypatch):
    migration = _load_migration()
    fake_op = Mock()
    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()

    fake_op.add_column.assert_called_once()
    table_name, column = fake_op.add_column.call_args.args
    assert table_name == "admin_users"
    assert column.name == "token_version"
    assert isinstance(column.type, Integer)
    assert column.nullable is False
    assert str(column.server_default.arg) == "0"


def test_migration_is_head_linked_and_reversible(monkeypatch):
    migration = _load_migration()
    fake_op = Mock()
    monkeypatch.setattr(migration, "op", fake_op)

    assert migration.revision == "v7a_admin_token_ver_001"
    assert migration.down_revision == "v6e_display_comments_001"

    migration.downgrade()

    fake_op.drop_column.assert_called_once_with("admin_users", "token_version")
