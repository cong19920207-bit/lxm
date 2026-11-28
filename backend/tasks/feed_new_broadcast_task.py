# -*- coding: utf-8 -*-
# 生活流·SSE 新帖广播调度任务（STEP-026）
#
# scheduler 每 30s 调 feed_new_broadcast_task：扫 feed_post 中
# generation_status='ready' AND is_visible=1 AND scheduled_publish_time<=NOW()
# AND sse_broadcasted=0 的帖子，调 feed_sse_service.broadcast_new_feed 推送后
# 批量置 sse_broadcasted=1（同帖单轮去重，防重复推送）。

import logging

from sqlalchemy import select, update

from backend.database import async_session_maker
from backend.models.feed_post import FeedPost
from backend.services.feed_service import feed_now, visible_post_condition
from backend.services.memory_business_guard import guard_business_write
from backend.services.feed_sse_service import feed_sse_service

logger = logging.getLogger(__name__)

_SCAN_LIMIT = 200


async def feed_new_broadcast_task() -> None:
    """扫描到点可见的新帖并 SSE 广播，随后置 sse_broadcasted=1。"""
    try:
        # 与 scheduled_publish_time（北京墙钟）对齐，勿用 utcnow
        now = feed_now()
        visible = await visible_post_condition(now)
        async with async_session_maker() as db:
            candidates = (await db.scalars(
                select(FeedPost.id).where(visible, FeedPost.sse_broadcasted == 0)
                .order_by(FeedPost.scheduled_publish_time, FeedPost.id).limit(_SCAN_LIMIT)
            )).all()
        if not candidates:
            return

        # Competing workers may read the same snapshot. Only the winner of the
        # conditional write for a still-public post may deliver its SSE hint.
        post_ids = []
        async with async_session_maker.begin() as db:
            await guard_business_write(db)
            for pid in candidates:
                claimed = await db.execute(
                    update(FeedPost).where(FeedPost.id == pid, FeedPost.sse_broadcasted == 0,
                                           visible).values(sse_broadcasted=1)
                    .execution_options(synchronize_session=False))
                if claimed.rowcount == 1:
                    post_ids.append(pid)
        if not post_ids:
            return

        feed_sse_service.broadcast_new_feed(post_ids)
        logger.info("[定时任务][FeedSSE] 广播新帖 %d 条 ids=%s", len(post_ids), post_ids)
    except Exception as e:
        logger.error("[定时任务][FeedSSE] 广播任务异常: %s", e, exc_info=True)
