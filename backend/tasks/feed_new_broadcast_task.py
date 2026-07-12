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
from backend.services.feed_service import feed_now
from backend.services.feed_sse_service import feed_sse_service

logger = logging.getLogger(__name__)

_SCAN_LIMIT = 200


async def feed_new_broadcast_task() -> None:
    """扫描到点可见的新帖并 SSE 广播，随后置 sse_broadcasted=1。"""
    try:
        # 与 scheduled_publish_time（北京墙钟）对齐，勿用 utcnow
        now = feed_now()
        async with async_session_maker() as db:
            rows = (await db.execute(
                select(FeedPost.id).where(
                    FeedPost.generation_status == "ready",
                    FeedPost.is_visible == 1,
                    FeedPost.scheduled_publish_time <= now,
                    FeedPost.sse_broadcasted == 0,
                ).order_by(FeedPost.scheduled_publish_time.asc()).limit(_SCAN_LIMIT)
            )).scalars().all()

        if not rows:
            return

        post_ids = list(rows)
        # 先置位再广播：即使广播后进程重启，也不会重复推送（用户依赖下拉刷新兜底）
        async with async_session_maker() as db:
            await db.execute(
                update(FeedPost)
                .where(FeedPost.id.in_(post_ids))
                .values(sse_broadcasted=1))
            await db.commit()

        feed_sse_service.broadcast_new_feed(post_ids)
        logger.info("[定时任务][FeedSSE] 广播新帖 %d 条 ids=%s", len(post_ids), post_ids)
    except Exception as e:
        logger.error("[定时任务][FeedSSE] 广播任务异常: %s", e, exc_info=True)
