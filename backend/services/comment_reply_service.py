# -*- coding: utf-8 -*-
# 生活流·评论回复延迟任务（STEP-018 · LLM-05）
#
# 独立轮询：每 30s 扫 feed_comment.due_at 到期的 pending 记录，调 LLM-05 生成回复，
# 45s×3 重试，内容安全兜底，状态机 pending→generating→ready/failed。

import logging
import time
from datetime import datetime

from sqlalchemy import select, update

from backend.constants.life_feed_config import (
    RELATIONSHIP_STAGE_ZH,
    level_to_stage,
)
from backend.database import async_session_maker
from backend.models.feed_comment import FeedComment
from backend.models.feed_post import FeedPost
from backend.models.relationship import Relationship
from backend.services import content_safety_service
from backend.services.deepseek_llm_service import deepseek_llm_service
from backend.services.life_prompt_service import render_prompt

logger = logging.getLogger(__name__)

_LLM05_TIMEOUT = 45.0
_LLM05_MAX_ATTEMPTS = 3
_BATCH_LIMIT = 50


class CommentReplyService:
    """评论回复延迟消费（LLM-05）"""

    async def poll_and_consume(self) -> int:
        """扫 due_at 到期的 pending 评论并逐条消费，返回处理条数。"""
        now = datetime.utcnow()
        async with async_session_maker() as db:
            stmt = (
                select(FeedComment.id)
                .where(FeedComment.gen_status == "pending",
                       FeedComment.due_at.is_not(None),
                       FeedComment.due_at <= now)
                .order_by(FeedComment.due_at.asc())
                .limit(_BATCH_LIMIT)
                .with_for_update(skip_locked=True)
            )
            ids = (await db.execute(stmt)).scalars().all()

        processed = 0
        for cid in ids:
            try:
                if await self.consume_one(cid):
                    processed += 1
            except Exception as e:
                logger.error("[LLM-05] 消费异常 comment_id=%s: %s", cid, e, exc_info=True)
        return processed

    async def consume_one(self, comment_id: int) -> bool:
        """消费单条评论，生成 LXM 回复。返回是否成功落库 ready。"""
        # a. 原子锁：pending → generating
        async with async_session_maker() as db:
            res = await db.execute(
                update(FeedComment)
                .where(FeedComment.id == comment_id,
                       FeedComment.gen_status == "pending")
                .values(gen_status="generating"))
            await db.commit()
            if not (res.rowcount and res.rowcount == 1):
                logger.info("[LLM-05] 已被其他 worker 处理，跳过 comment_id=%s", comment_id)
                return False

        # b. 载入上下文
        async with async_session_maker() as db:
            comment = (await db.execute(
                select(FeedComment).where(FeedComment.id == comment_id)
            )).scalars().first()
            if comment is None:
                return False
            post = (await db.execute(
                select(FeedPost).where(FeedPost.id == comment.post_id)
            )).scalars().first()
            rel = (await db.execute(
                select(Relationship).where(Relationship.user_id == comment.user_id)
            )).scalars().first()

        level = int(rel.level) if rel and rel.level is not None else 0
        stage = level_to_stage(level)
        stage_zh = RELATIONSHIP_STAGE_ZH.get(stage, "陌生")
        hobby = (rel.user_hobby_name if rel else None) or ""
        real = (rel.user_real_name if rel else None) or ""
        has_call = bool(hobby or real)

        logger.info("[LLM-05] pending→generating comment_id=%s 关系档=%s", comment_id, stage_zh)

        variables = {
            "post_text": post.content_text if post else "",
            "user_comment": comment.content,
            "relationship_stage": stage_zh,
        }
        if has_call:
            variables["user_hobby_name"] = hobby
            variables["user_real_name"] = real
        optional = {"称呼": has_call, "记忆": False}

        try:
            system_prompt = await render_prompt("prompt_p06_system", {})
            user_prompt = await render_prompt("prompt_p06_user", variables, optional)
        except Exception as e:
            logger.error("[LLM-05] Prompt 渲染失败 comment_id=%s: %s", comment_id, e)
            await self._mark_failed(comment_id)
            return False

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # e. 重试循环：最多 3 次，单次 45s
        reply = None
        for attempt in range(1, _LLM05_MAX_ATTEMPTS + 1):
            start = time.time()
            try:
                raw = await deepseek_llm_service.call_llm(
                    "llm_05", messages, temperature=0.8, timeout=_LLM05_TIMEOUT)
                if raw and raw.strip():
                    reply = raw.strip()
                    logger.info(
                        "[LLM-05] 调用成功 comment_id=%s 耗时=%.2fs 尝试=%d",
                        comment_id, time.time() - start, attempt)
                    break
                logger.warning(
                    "[LLM-05] 返回空 comment_id=%s 尝试=%d/%d",
                    comment_id, attempt, _LLM05_MAX_ATTEMPTS)
            except Exception as e:
                logger.warning(
                    "[LLM-05] 单次失败 comment_id=%s 尝试=%d/%d: %s",
                    comment_id, attempt, _LLM05_MAX_ATTEMPTS, e)

        # f. 3 次全失败
        if not reply:
            logger.error("[LLM-05] 最终失败（静默不回，可后台补发）comment_id=%s", comment_id)
            await self._mark_failed(comment_id)
            return False

        # g. 内容安全
        safe = await content_safety_service.check_content(reply)
        if not safe.get("is_safe", True):
            logger.error("[LLM-05] 内容安全违规 comment_id=%s: %s",
                         comment_id, safe.get("reason"))
            await self._mark_failed(comment_id)
            return False

        # h. 落库 ready
        async with async_session_maker() as db:
            await db.execute(
                update(FeedComment)
                .where(FeedComment.id == comment_id)
                .values(lxm_reply=reply, lxm_reply_at=datetime.utcnow(), gen_status="ready"))
            await db.commit()
        logger.info("[LLM-05] 回复落库 ready comment_id=%s", comment_id)
        return True

    @staticmethod
    async def _mark_failed(comment_id: int) -> None:
        async with async_session_maker() as db:
            await db.execute(
                update(FeedComment)
                .where(FeedComment.id == comment_id)
                .values(gen_status="failed"))
            await db.commit()


# 全局单例
comment_reply_service = CommentReplyService()


async def comment_reply_poll_task() -> None:
    """scheduler 每 30s 调用入口。"""
    try:
        n = await comment_reply_service.poll_and_consume()
        if n:
            logger.info("[定时任务][LLM-05] 本轮消费评论回复 %d 条", n)
    except Exception as e:
        logger.error("[定时任务][LLM-05] 轮询任务异常: %s", e, exc_info=True)
