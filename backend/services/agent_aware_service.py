# -*- coding: utf-8 -*-
# 生活流·点赞/已读感知排队消费服务（STEP-019 · LLM-06/07 基建）
#
# 独立排队表消费架构（PRD 6.1.3/7.x、§11.4）：
#   - 与对话主链 Agent（AGE003/Step8/Future）完全解耦：
#     不评分（calculate_action_score）、不共享日上限 8 次计数、不共享 30min 间隔、
#     不受黑名单限制、不做 Step8 记忆检索与双 LLM 融合。
#   - enqueue：写 agent_aware_queue（pending，due_at=now+delay），快照关系档与 prompt_key。
#   - 独立轮询任务每 60s 调 consume_pending，逐条 consume_record：
#     原子锁 pending→generating → 按 trigger_type 分派 like/read 生成 →
#     落 agent_message（action_score=0）+ 分配 sort_seq → queue.status=sent；失败→failed。

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update

from backend.constants.life_feed_config import RELATIONSHIP_STAGE_ZH
from backend.database import async_session_maker
from backend.models.agent_aware_queue import AgentAwareQueue
from backend.models.agent_message import AgentMessage, TriggerType
from backend.models.feed_post import FeedPost
from backend.models.relationship import Relationship
from backend.services import content_safety_service
from backend.services.deepseek_llm_service import deepseek_llm_service
from backend.services.life_prompt_service import render_prompt
from backend.services.timeline_seq_service import allocate_sort_seq

logger = logging.getLogger(__name__)

_BATCH_LIMIT = 20
_AWARE_TIMEOUT = 45.0
_AWARE_MAX_ATTEMPTS = 2


async def generate_aware_text(
    row: AgentAwareQueue,
    node_key: str,
    temperature: float,
) -> Optional[str]:
    """
    感知 IM 文本生成通用逻辑（LIKE_AWARE/READ_AWARE 共用）：
    载入帖子/关系 → 渲染 prompt_key 的 system/user → 调对应 LLM 节点（45s×2 重试）
    → 内容安全兜底 → 返回文本；任一环节失败或违规返回 None。

    Args:
        row: agent_aware_queue 记录（含 post_id / relationship_stage / prompt_key）
        node_key: DeepSeek 节点标识（llm_06 / llm_07）
        temperature: 采样温度
    """
    import time

    async with async_session_maker() as db:
        post = (await db.execute(
            select(FeedPost).where(FeedPost.id == row.post_id)
        )).scalars().first()
        rel = (await db.execute(
            select(Relationship).where(Relationship.user_id == row.user_id)
        )).scalars().first()

    if post is None:
        logger.warning("[感知IM] 帖子不存在，跳过生成 queue_id=%s post=%s", row.id, row.post_id)
        return None

    stage = row.relationship_stage or "stranger"
    stage_zh = RELATIONSHIP_STAGE_ZH.get(stage, "陌生")
    hobby = (rel.user_hobby_name if rel else None) or ""
    real = (rel.user_real_name if rel else None) or ""
    has_call = bool(hobby or real)
    prompt_key = row.prompt_key or "prompt_p07"

    variables = {
        "post_text": post.content_text or "",
        "relationship_stage": stage_zh,
    }
    if has_call:
        variables["user_hobby_name"] = hobby
        variables["user_real_name"] = real
    optional = {"称呼": has_call}

    try:
        system_prompt = await render_prompt(f"{prompt_key}_system", {})
        user_prompt = await render_prompt(f"{prompt_key}_user", variables, optional)
    except Exception as e:
        logger.error("[感知IM] Prompt 渲染失败 queue_id=%s prompt=%s: %s",
                     row.id, prompt_key, e)
        return None

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    text = None
    for attempt in range(1, _AWARE_MAX_ATTEMPTS + 1):
        start = time.time()
        try:
            raw = await deepseek_llm_service.call_llm(
                node_key, messages, temperature=temperature, timeout=_AWARE_TIMEOUT)
            if raw and raw.strip():
                text = raw.strip()
                logger.info("[感知IM] LLM 调用成功 queue_id=%s node=%s 耗时=%.2fs 尝试=%d",
                            row.id, node_key, time.time() - start, attempt)
                break
            logger.warning("[感知IM] LLM 返回空 queue_id=%s 尝试=%d/%d",
                           row.id, attempt, _AWARE_MAX_ATTEMPTS)
        except Exception as e:
            logger.warning("[感知IM] LLM 单次失败 queue_id=%s 尝试=%d/%d: %s",
                           row.id, attempt, _AWARE_MAX_ATTEMPTS, e)

    if not text:
        logger.error("[感知IM] LLM 最终失败 queue_id=%s node=%s", row.id, node_key)
        return None

    safe = await content_safety_service.check_content(text)
    if not safe.get("is_safe", True):
        logger.error("[感知IM] 内容安全违规 queue_id=%s: %s", row.id, safe.get("reason"))
        return None

    return text


class AgentAwareService:
    """点赞/已读感知排队消费服务（独立于对话主链 Agent）"""

    async def enqueue(
        self,
        user_id: int,
        aware_type: str,
        related_post_id: Optional[int],
        prompt_key: str,
        delay_seconds: int,
        relationship_stage: str,
        extra_context: Optional[dict] = None,
    ) -> int:
        """
        入队一条感知 IM 记录。

        Args:
            user_id: 触发用户
            aware_type: LIKE_AWARE / READ_AWARE
            related_post_id: 关联 feed_post.id
            prompt_key: 生成使用的 Prompt config_key 前缀（prompt_p07 / p08~p11 / p14）
            delay_seconds: 相对当前时刻的延迟（秒）
            relationship_stage: 入队时的关系档快照（stranger/friend/intimate/soulmate）
            extra_context: 附加上下文快照（is_special / snapshot_summary 等）

        Returns:
            queue_id
        """
        due_at = datetime.utcnow() + timedelta(seconds=int(delay_seconds))
        async with async_session_maker() as db:
            row = AgentAwareQueue(
                user_id=user_id,
                trigger_type=aware_type,
                post_id=related_post_id,
                relationship_stage=relationship_stage,
                due_at=due_at,
                status="pending",
                prompt_key=prompt_key,
                extra_context=extra_context,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            queue_id = row.id
        logger.info(
            "[感知IM] 入队 queue_id=%s type=%s user=%s post=%s due_at=%s prompt=%s",
            queue_id, aware_type, user_id, related_post_id, due_at, prompt_key,
        )
        return queue_id

    async def consume_pending(self, batch_size: int = _BATCH_LIMIT) -> int:
        """轮询消费入口：扫到期 pending 记录逐条消费，返回成功发送条数。"""
        now = datetime.utcnow()
        async with async_session_maker() as db:
            stmt = (
                select(AgentAwareQueue.id)
                .where(AgentAwareQueue.status == "pending",
                       AgentAwareQueue.due_at <= now)
                .order_by(AgentAwareQueue.due_at.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            ids = (await db.execute(stmt)).scalars().all()

        processed = 0
        for qid in ids:
            try:
                if await self.consume_record(qid):
                    processed += 1
            except Exception as e:
                logger.error("[感知IM] 消费异常 queue_id=%s: %s", qid, e, exc_info=True)
        return processed

    async def consume_record(self, queue_id: int) -> bool:
        """消费单条：原子锁 → 分派生成 → 落 agent_message + sort_seq → sent。"""
        # a. 原子锁：pending → generating（并发只允许一方成功）
        async with async_session_maker() as db:
            res = await db.execute(
                update(AgentAwareQueue)
                .where(AgentAwareQueue.id == queue_id,
                       AgentAwareQueue.status == "pending")
                .values(status="generating"))
            await db.commit()
            if not (res.rowcount and res.rowcount == 1):
                logger.info("[感知IM] 已被其他 worker 处理，跳过 queue_id=%s", queue_id)
                return False

        # b. 载入记录
        async with async_session_maker() as db:
            row = (await db.execute(
                select(AgentAwareQueue).where(AgentAwareQueue.id == queue_id)
            )).scalars().first()
        if row is None:
            return False

        logger.info("[感知IM] 消费开始 queue_id=%s type=%s", queue_id, row.trigger_type)

        # c. 按 trigger_type 分派生成
        try:
            if row.trigger_type == TriggerType.LIKE_AWARE:
                from backend.services.like_aware_service import like_aware_service
                text = await like_aware_service.generate_and_send(row)
            elif row.trigger_type == TriggerType.READ_AWARE:
                from backend.services.read_aware_service import read_aware_service
                text = await read_aware_service.generate_and_send(row)
            else:
                logger.error("[感知IM] 未知 trigger_type=%s queue_id=%s",
                             row.trigger_type, queue_id)
                await self._mark_failed(queue_id, "unknown_trigger_type")
                return False
        except Exception as e:
            logger.error("[感知IM] 生成异常 queue_id=%s: %s", queue_id, e, exc_info=True)
            await self._mark_failed(queue_id, f"gen_error:{e}"[:255])
            return False

        if not text:
            logger.warning("[感知IM] 生成失败/内容违规 queue_id=%s", queue_id)
            await self._mark_failed(queue_id, "gen_failed_or_unsafe")
            return False

        # d. 落 agent_message（action_score=0）+ 分配 sort_seq → queue=sent
        async with async_session_maker() as db:
            seqs = await allocate_sort_seq(row.user_id, 1, db)
            msg = AgentMessage(
                user_id=row.user_id,
                trigger_type=row.trigger_type,
                content=text,
                action_score=0.0,
                is_read=False,
                sort_seq=seqs[0],
                created_at=datetime.utcnow(),
            )
            db.add(msg)
            await db.flush()
            await db.execute(
                update(AgentAwareQueue)
                .where(AgentAwareQueue.id == queue_id)
                .values(status="sent", agent_message_id=msg.id))
            await db.commit()
            msg_id = msg.id
            seq = seqs[0]

        logger.info(
            "[感知IM] 发送成功 queue_id=%s agent_message_id=%s sort_seq=%s",
            queue_id, msg_id, seq,
        )
        return True

    @staticmethod
    async def _mark_failed(queue_id: int, reason: str) -> None:
        async with async_session_maker() as db:
            await db.execute(
                update(AgentAwareQueue)
                .where(AgentAwareQueue.id == queue_id)
                .values(status="failed", fail_reason=(reason or "")[:255]))
            await db.commit()


# 全局单例
agent_aware_service = AgentAwareService()
