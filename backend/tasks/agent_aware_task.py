# -*- coding: utf-8 -*-
# 生活流·点赞/已读感知独立轮询任务（STEP-019）
#
# scheduler 每 60s 调 agent_aware_poll_task：扫 agent_aware_queue 中 status=pending
# 且 due_at<=NOW() 的记录（FOR UPDATE SKIP LOCKED），逐条 consume_record 生成并发送。
# 与对话主链 Agent 的 P0~P4/Future 扫描互不干扰。

import logging

from backend.services.agent_aware_service import agent_aware_service

logger = logging.getLogger(__name__)


async def agent_aware_poll_task() -> None:
    """scheduler 每 60s 调用入口：消费到期的感知 IM 队列。"""
    try:
        n = await agent_aware_service.consume_pending()
        if n:
            logger.info("[定时任务][感知IM] 本轮发送感知消息 %d 条", n)
    except Exception as e:
        logger.error("[定时任务][感知IM] 轮询任务异常: %s", e, exc_info=True)
