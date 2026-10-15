# -*- coding: utf-8 -*-
# MySQL 异步连接池，SQLAlchemy 引擎和 Session 管理

from collections.abc import AsyncGenerator

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_mysql_url


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


# 创建异步引擎（asyncmy 驱动）
engine = create_async_engine(
    get_mysql_url(),
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# 异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    依赖注入：获取数据库会话，请求结束后自动关闭。
    用法：router 中 def xxx(db: AsyncSession = Depends(get_db))
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_all_tables() -> None:
    """
    首次启动时创建所有数据表。
    导入 models 包以触发表注册到 Base.metadata。
    旧库若缺 sort_seq 相关列/表，启动时幂等补齐并必要时回填历史数据。
    """
    import backend.models  # noqa: F401
    from backend.models.realtime_voice import VOICE_TABLE_NAMES
    from backend.models.memory_config import MEMORY_CONFIG_TABLE_NAMES
    from backend.models.memory_control import MEMORY_CONTROL_TABLE_NAMES
    from backend.models.memory_maintenance import MEMORY_MAINTENANCE_TABLE_NAMES
    from backend.models.memory_backfill import MEMORY_BACKFILL_TABLE_NAMES

    memory_tables = {'memory_diagnostic_run'} | MEMORY_CONFIG_TABLE_NAMES | MEMORY_CONTROL_TABLE_NAMES | MEMORY_MAINTENANCE_TABLE_NAMES | MEMORY_BACKFILL_TABLE_NAMES
    from backend.models.chat_lifecycle import CHAT_LIFECYCLE_TABLE_NAMES
    managed_tables = VOICE_TABLE_NAMES | memory_tables | CHAT_LIFECYCLE_TABLE_NAMES

    runtime_tables = [
        table
        for table_name, table in Base.metadata.tables.items()
        if table_name not in managed_tables
    ]

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=runtime_tables,
            )
        )
        missing_voice_tables = await conn.run_sync(
            lambda sync_conn: sorted(
                VOICE_TABLE_NAMES - set(inspect(sync_conn).get_table_names())
            )
        )
        if missing_voice_tables:
            raise RuntimeError(
                "实时语音数据库迁移未完成，缺少 Alembic 管理表: "
                + ", ".join(missing_voice_tables)
            )
        missing_memory_tables = await conn.run_sync(
            lambda sync_conn: sorted(memory_tables - set(inspect(sync_conn).get_table_names()))
        )
        if missing_memory_tables:
            raise RuntimeError("记忆配置数据库迁移未完成，请执行 Alembic upgrade head: " + ", ".join(missing_memory_tables))
        call_columns = await conn.run_sync(lambda sync_conn: {
            column['name'] for column in inspect(sync_conn).get_columns('voice_call')})
        if 'cleared_run_id' not in call_columns:
            raise RuntimeError('记忆清理迁移未完成，缺少 voice_call.cleared_run_id（v9d）')
        if 'call01_fallback' not in call_columns:
            raise RuntimeError('实时语音数据库迁移未完成，缺少 voice_call.call01_fallback（v8f）')
        memory_columns = await conn.run_sync(lambda sync_conn: {
            column['name'] for column in inspect(sync_conn).get_columns('voice_memory_job')})
        if 'extraction_snapshot' not in memory_columns:
            raise RuntimeError('实时语音数据库迁移未完成，缺少 voice_memory_job.extraction_snapshot（v8e）')

        missing_chat = await conn.run_sync(lambda c: sorted(CHAT_LIFECYCLE_TABLE_NAMES - set(inspect(c).get_table_names())))
        if missing_chat:
            raise RuntimeError("文字生命周期迁移未完成，请执行 Alembic upgrade head: " + ", ".join(missing_chat))

    from backend.schema_timeline import ensure_timeline_sort_seq_ddl
    from backend.services.timeline_backfill_service import backfill_sort_seq_if_needed

    await ensure_timeline_sort_seq_ddl(engine)
    await backfill_sort_seq_if_needed()
