# -*- coding: utf-8 -*-
# Alembic 运行环境：使用 PyMySQL 同步引擎，与异步运行时 asyncmy 分离

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from backend.config import get_mysql_sync_migration_url
from backend.database import Base

# 导入全部模型以注册 metadata
import backend.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_mysql_sync_migration_url()


def run_migrations_offline() -> None:
    """生成 SQL 脚本模式（无 live DB）。"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """连库执行 upgrade/downgrade。"""
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
