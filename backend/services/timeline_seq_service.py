# -*- coding: utf-8 -*-
# 时间线序号分配服务：为 conversation_log / agent_message 分配 per-user 单调递增的 sort_seq
# 使用 user_timeline_seq 表 + SELECT ... FOR UPDATE 保证并发安全

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user_timeline_seq import UserTimelineSeq

logger = logging.getLogger(__name__)


async def allocate_sort_seq(user_id: int, count: int, db: AsyncSession) -> list[int]:
    """
    原子分配 count 个连续 sort_seq 序号。

    调用方必须在同一事务中使用返回值并 commit，以保证序号与业务写入的原子性。
    若 user_timeline_seq 中无该用户记录，会自动初始化。

    Args:
        user_id: 用户 ID
        count: 需要分配的序号个数（例如对话一轮传 2，主动消息传 1）
        db: 当前事务的 AsyncSession（调用方负责 commit）

    Returns:
        长度为 count 的升序序号列表，例如 [5, 6]
    """
    if count < 1:
        raise ValueError("count 必须 >= 1")

    # 行级锁读取当前计数器
    stmt = (
        select(UserTimelineSeq)
        .where(UserTimelineSeq.user_id == user_id)
        .with_for_update()
    )
    result = await db.execute(stmt)
    seq_row = result.scalar_one_or_none()

    if seq_row is None:
        # 首次使用：初始化序列行
        seq_row = UserTimelineSeq(user_id=user_id, next_seq=1)
        db.add(seq_row)
        await db.flush()
        # 重新以 FOR UPDATE 读取（flush 后行已存在）
        result = await db.execute(stmt)
        seq_row = result.scalar_one_or_none()

    start = seq_row.next_seq
    seq_row.next_seq = start + count

    allocated = list(range(start, start + count))
    logger.debug("分配 sort_seq: user_id=%d, seq=%s", user_id, allocated)
    return allocated
