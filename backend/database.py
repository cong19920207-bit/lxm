# -*- coding: utf-8 -*-
# MySQL 异步连接池，SQLAlchemy 引擎和 Session 管理

from collections.abc import AsyncGenerator

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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from backend.schema_timeline import ensure_timeline_sort_seq_ddl
    from backend.services.timeline_backfill_service import backfill_sort_seq_if_needed

    await ensure_timeline_sort_seq_ddl(engine)
    await backfill_sort_seq_if_needed()
