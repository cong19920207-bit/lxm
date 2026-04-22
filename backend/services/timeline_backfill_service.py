# -*- coding: utf-8 -*-
# 时间线 sort_seq 历史数据回填（与 scripts/backfill_sort_seq 规则一致，供启动时与脚本复用）

import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_maker
from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from backend.models.user import User
from backend.models.user_timeline_seq import UserTimelineSeq

logger = logging.getLogger(__name__)


async def backfill_user(user_id: int, db: AsyncSession) -> int:
    """
    为单个用户回填 sort_seq 并初始化 user_timeline_seq。
    返回该用户分配的序号总数。
    """
    conv_stmt = (
        select(ConversationLog.id, ConversationLog.created_at)
        .where(ConversationLog.user_id == user_id)
        .order_by(ConversationLog.created_at.asc(), ConversationLog.id.asc())
    )
    conv_result = await db.execute(conv_stmt)
    conv_items = [
        {"table": "conv", "id": row.id, "created_at": row.created_at}
        for row in conv_result.all()
    ]

    agent_stmt = (
        select(AgentMessage.id, AgentMessage.created_at)
        .where(AgentMessage.user_id == user_id)
        .order_by(AgentMessage.created_at.asc(), AgentMessage.id.asc())
    )
    agent_result = await db.execute(agent_stmt)
    agent_items = [
        {"table": "agent", "id": row.id, "created_at": row.created_at}
        for row in agent_result.all()
    ]

    if not conv_items and not agent_items:
        seq_row = await db.get(UserTimelineSeq, user_id)
        if not seq_row:
            db.add(UserTimelineSeq(user_id=user_id, next_seq=1))
        return 0

    def sort_key(item):
        table_order = 0 if item["table"] == "conv" else 1
        return (item["created_at"], table_order, item["id"])

    all_items = conv_items + agent_items
    all_items.sort(key=sort_key)

    seq = 1
    conv_updates = []
    agent_updates = []

    for item in all_items:
        if item["table"] == "conv":
            conv_updates.append({"_id": item["id"], "_sort_seq": seq})
        else:
            agent_updates.append({"_id": item["id"], "_sort_seq": seq})
        seq += 1

    if conv_updates:
        for batch_start in range(0, len(conv_updates), 500):
            batch = conv_updates[batch_start : batch_start + 500]
            for u in batch:
                await db.execute(
                    update(ConversationLog)
                    .where(ConversationLog.id == u["_id"])
                    .values(sort_seq=u["_sort_seq"])
                )

    if agent_updates:
        for batch_start in range(0, len(agent_updates), 500):
            batch = agent_updates[batch_start : batch_start + 500]
            for u in batch:
                await db.execute(
                    update(AgentMessage)
                    .where(AgentMessage.id == u["_id"])
                    .values(sort_seq=u["_sort_seq"])
                )

    seq_row = await db.get(UserTimelineSeq, user_id)
    if seq_row:
        seq_row.next_seq = seq
    else:
        db.add(UserTimelineSeq(user_id=user_id, next_seq=seq))

    return seq - 1


async def _count_zero_sort_seq(db: AsyncSession) -> int:
    c_conv = await db.execute(
        select(func.count()).select_from(ConversationLog).where(ConversationLog.sort_seq == 0)
    )
    c_agent = await db.execute(
        select(func.count()).select_from(AgentMessage).where(AgentMessage.sort_seq == 0)
    )
    return (c_conv.scalar() or 0) + (c_agent.scalar() or 0)


async def run_full_backfill() -> None:
    """为所有用户执行回填（可重复执行，会按时间规则覆盖 sort_seq）。"""
    logger.info("=== 开始回填 sort_seq ===")

    async with async_session_maker() as db:
        user_stmt = select(User.id).order_by(User.id.asc())
        user_result = await db.execute(user_stmt)
        user_ids = [row[0] for row in user_result.all()]

    logger.info("共 %d 个用户需要处理", len(user_ids))

    total_records = 0
    for i, uid in enumerate(user_ids, 1):
        async with async_session_maker() as db:
            try:
                count = await backfill_user(uid, db)
                await db.commit()
                total_records += count
                if i % 10 == 0 or i == len(user_ids):
                    logger.info("进度: %d/%d 用户, 已处理 %d 条记录", i, len(user_ids), total_records)
            except Exception:
                await db.rollback()
                logger.exception("回填用户 %d 失败", uid)

    logger.info("=== 回填完成：共 %d 个用户、%d 条记录 ===", len(user_ids), total_records)


async def backfill_sort_seq_if_needed() -> None:
    """
    仅在仍存在 sort_seq=0 的记录时执行全量回填。
    新库或已回填库无 0 值，启动时几乎无开销。
    """
    async with async_session_maker() as db:
        zeros = await _count_zero_sort_seq(db)
    if zeros == 0:
        return
    logger.info("检测到 %d 条 sort_seq=0 的记录，启动自动回填", zeros)
    await run_full_backfill()
