# -*- coding: utf-8 -*-
# 启动时幂等补齐时间线 sort_seq 相关 DDL（兼容未执行 migrate_add_sort_seq.sql 的旧库）

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def ensure_timeline_sort_seq_ddl(engine: AsyncEngine) -> None:
    """
    若当前库缺少 conversation_log / agent_message 的 sort_seq 列或索引，则自动补齐。
    与 scripts/migrate_add_sort_seq.sql 效果一致，可重复执行。
    """
    async with engine.begin() as conn:

        async def column_exists(table: str, column: str) -> bool:
            r = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
                ),
                {"t": table, "c": column},
            )
            return r.first() is not None

        async def index_exists(table: str, index_name: str) -> bool:
            r = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND INDEX_NAME = :i "
                    "LIMIT 1"
                ),
                {"t": table, "i": index_name},
            )
            return r.first() is not None

        if not await column_exists("conversation_log", "sort_seq"):
            logger.info("DDL: conversation_log 增加 sort_seq 列")
            await conn.execute(
                text("ALTER TABLE conversation_log ADD COLUMN sort_seq BIGINT NOT NULL DEFAULT 0")
            )
        if not await index_exists("conversation_log", "ix_conversation_log_sort_seq"):
            logger.info("DDL: 创建索引 ix_conversation_log_sort_seq")
            await conn.execute(
                text("CREATE INDEX ix_conversation_log_sort_seq ON conversation_log (sort_seq)")
            )

        if not await column_exists("agent_message", "sort_seq"):
            logger.info("DDL: agent_message 增加 sort_seq 列")
            await conn.execute(
                text("ALTER TABLE agent_message ADD COLUMN sort_seq BIGINT NOT NULL DEFAULT 0")
            )
        if not await index_exists("agent_message", "ix_agent_message_sort_seq"):
            logger.info("DDL: 创建索引 ix_agent_message_sort_seq")
            await conn.execute(
                text("CREATE INDEX ix_agent_message_sort_seq ON agent_message (sort_seq)")
            )
