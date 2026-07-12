# -*- coding: utf-8 -*-
# 生活流·已读感知 IM 服务（LLM-07 · STEP-021）
#
# PRD 7.1~7.4 / 6.1.4 已读感知规则：
#   - 同帖 READ_AWARE 去重（pending/generating/sent 任一存在即跳过）
#   - 6h 点赞互斥：近 read_suppress_after_like_im_hours 小时内已有 LIKE_AWARE(pending/sent) → 跳过
#   - 用户级冷却：近 read_aware_user_cooldown_hours（默认 6）内已有任意帖
#     READ_AWARE(pending/generating/sent)（按入队 created_at）→ 跳过，整用户最多 1 条
#   - 多帖取最近发布一条（按 scheduled_publish_time DESC）作为 anchor
#   - 特殊档（注册窗口内 + 次数未满）：100% 触发，延迟 read_aware_special_delay_sec，
#     read_aware_special_used_count 原子 +1，Prompt=P-14
#   - 常规档：关系档 → P-08/09/10/11，延迟 read_regular_delay_{stage}_{min,max}
# on_feed_read 由 STEP-029 已读上报调用；generate_and_send 由 STEP-019 消费分派调用。

import logging
import random
from datetime import datetime, timedelta

from sqlalchemy import select, update

from backend.constants.life_feed_config import (
    CONFIG_READ_AWARE_SPECIAL_DELAY_SEC,
    CONFIG_READ_AWARE_SPECIAL_MAX_COUNT,
    CONFIG_READ_AWARE_SPECIAL_WINDOW_HOURS,
    CONFIG_READ_AWARE_USER_COOLDOWN_HOURS,
    CONFIG_READ_SUPPRESS_AFTER_LIKE_IM_HOURS,
    DEFAULT_READ_AWARE_SPECIAL_DELAY_SEC,
    DEFAULT_READ_AWARE_SPECIAL_MAX_COUNT,
    DEFAULT_READ_AWARE_SPECIAL_WINDOW_HOURS,
    DEFAULT_READ_AWARE_USER_COOLDOWN_HOURS,
    DEFAULT_READ_REGULAR_DELAY_SEC,
    DEFAULT_READ_SUPPRESS_AFTER_LIKE_IM_HOURS,
    level_to_stage,
    read_regular_delay_key,
)
from backend.database import async_session_maker
from backend.models.agent_aware_queue import AgentAwareQueue
from backend.models.agent_message import TriggerType
from backend.models.feed_post import FeedPost
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.services.agent_aware_service import agent_aware_service, generate_aware_text
from backend.services.life_feed_config_service import get_life_feed_config

logger = logging.getLogger(__name__)

_READ_SPECIAL_PROMPT_KEY = "prompt_p14"
# 关系档 → 常规已读 Prompt config_key
_READ_REGULAR_PROMPT_KEY = {
    "stranger": "prompt_p08",
    "friend": "prompt_p09",
    "intimate": "prompt_p10",
    "soulmate": "prompt_p11",
}


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class ReadAwareService:
    """已读感知 IM（LLM-07）"""

    async def on_feed_read(self, user_id: int, post_id: int) -> None:
        """单帖已读上报入口（STEP-029 调用）。异常吞掉并记日志，不影响上报接口。"""
        try:
            await self._process(user_id, [post_id])
        except Exception as e:
            logger.error("[已读IM] on_feed_read 异常（不影响上报）user=%s post=%s: %s",
                         user_id, post_id, e, exc_info=True)

    async def on_feed_read_batch(self, user_id: int, post_ids: list[int]) -> None:
        """批量已读上报：取最近发布一帖入队（PRD 7.3）。"""
        try:
            await self._process(user_id, post_ids)
        except Exception as e:
            logger.error("[已读IM] on_feed_read_batch 异常 user=%s posts=%s: %s",
                         user_id, post_ids, e, exc_info=True)

    async def _process(self, user_id: int, post_ids: list[int]) -> None:
        if not post_ids:
            return

        # 多帖取最近发布一条作为 anchor
        async with async_session_maker() as db:
            anchor = (await db.execute(
                select(FeedPost)
                .where(FeedPost.id.in_(post_ids))
                .order_by(FeedPost.scheduled_publish_time.desc())
                .limit(1)
            )).scalars().first()
        if anchor is None:
            logger.info("[已读IM] 无有效帖子，跳过 user=%s posts=%s", user_id, post_ids)
            return
        post_id = anchor.id

        # 1. 同帖 READ_AWARE 去重
        async with async_session_maker() as db:
            dup = (await db.execute(
                select(AgentAwareQueue.id).where(
                    AgentAwareQueue.user_id == user_id,
                    AgentAwareQueue.post_id == post_id,
                    AgentAwareQueue.trigger_type == TriggerType.READ_AWARE,
                    AgentAwareQueue.status.in_(["pending", "generating", "sent"]),
                ).limit(1)
            )).scalars().first()
        if dup:
            logger.info("[已读IM] 跳过 user=%s post=%s reason=already_queued", user_id, post_id)
            return

        # 2. 6h 点赞互斥
        suppress_hours = _to_int(
            await get_life_feed_config(CONFIG_READ_SUPPRESS_AFTER_LIKE_IM_HOURS,
                                       DEFAULT_READ_SUPPRESS_AFTER_LIKE_IM_HOURS),
            DEFAULT_READ_SUPPRESS_AFTER_LIKE_IM_HOURS)
        since = datetime.utcnow() - timedelta(hours=suppress_hours)
        async with async_session_maker() as db:
            like_recent = (await db.execute(
                select(AgentAwareQueue.id).where(
                    AgentAwareQueue.user_id == user_id,
                    AgentAwareQueue.trigger_type == TriggerType.LIKE_AWARE,
                    AgentAwareQueue.status.in_(["pending", "sent"]),
                    AgentAwareQueue.created_at >= since,
                ).limit(1)
            )).scalars().first()
        if like_recent:
            logger.info("[已读IM] 跳过 user=%s post=%s reason=like_im_suppress_6h",
                        user_id, post_id)
            return

        # 2.5 用户级冷却：滚动窗口内已有任意 READ_AWARE → 整用户最多 1 条
        cooldown_hours = _to_int(
            await get_life_feed_config(CONFIG_READ_AWARE_USER_COOLDOWN_HOURS,
                                       DEFAULT_READ_AWARE_USER_COOLDOWN_HOURS),
            DEFAULT_READ_AWARE_USER_COOLDOWN_HOURS)
        if cooldown_hours > 0:
            cooldown_since = datetime.utcnow() - timedelta(hours=cooldown_hours)
            async with async_session_maker() as db:
                recent_read = (await db.execute(
                    select(AgentAwareQueue.id).where(
                        AgentAwareQueue.user_id == user_id,
                        AgentAwareQueue.trigger_type == TriggerType.READ_AWARE,
                        AgentAwareQueue.status.in_(["pending", "generating", "sent"]),
                        AgentAwareQueue.created_at >= cooldown_since,
                    ).limit(1)
                )).scalars().first()
            if recent_read:
                logger.info(
                    "[已读IM] 跳过 user=%s post=%s reason=user_cooldown_%sh",
                    user_id, post_id, cooldown_hours)
                return

        # 载入用户 + 关系
        async with async_session_maker() as db:
            user = (await db.execute(
                select(User).where(User.id == user_id))).scalars().first()
            rel = (await db.execute(
                select(Relationship).where(Relationship.user_id == user_id))).scalars().first()
        if user is None:
            logger.warning("[已读IM] 用户不存在，跳过 user=%s", user_id)
            return

        level = int(rel.level) if rel and rel.level is not None else 0
        stage = level_to_stage(level)

        window_hours = _to_int(
            await get_life_feed_config(CONFIG_READ_AWARE_SPECIAL_WINDOW_HOURS,
                                       DEFAULT_READ_AWARE_SPECIAL_WINDOW_HOURS),
            DEFAULT_READ_AWARE_SPECIAL_WINDOW_HOURS)
        special_max = _to_int(
            await get_life_feed_config(CONFIG_READ_AWARE_SPECIAL_MAX_COUNT,
                                       DEFAULT_READ_AWARE_SPECIAL_MAX_COUNT),
            DEFAULT_READ_AWARE_SPECIAL_MAX_COUNT)
        special_delay = _to_int(
            await get_life_feed_config(CONFIG_READ_AWARE_SPECIAL_DELAY_SEC,
                                       DEFAULT_READ_AWARE_SPECIAL_DELAY_SEC),
            DEFAULT_READ_AWARE_SPECIAL_DELAY_SEC)

        used_count = int(rel.read_aware_special_used_count) if rel else 0
        within_window = (
            user.created_at is not None
            and datetime.utcnow() - user.created_at <= timedelta(hours=window_hours)
        )

        # 3. 特殊档判定（P-14；PRD 7.2：入队成功才消耗次数；失败回滚占位）
        if within_window and used_count < special_max and rel is not None:
            async with async_session_maker() as db:
                res = await db.execute(
                    update(Relationship)
                    .where(Relationship.user_id == user_id,
                           Relationship.read_aware_special_used_count < special_max)
                    .values(read_aware_special_used_count=Relationship.read_aware_special_used_count + 1))
                await db.commit()
            if res.rowcount and res.rowcount == 1:
                try:
                    qid = await agent_aware_service.enqueue(
                        user_id=user_id,
                        aware_type=TriggerType.READ_AWARE,
                        related_post_id=post_id,
                        prompt_key=_READ_SPECIAL_PROMPT_KEY,
                        delay_seconds=special_delay,
                        relationship_stage=stage,
                        extra_context={"is_special": True},
                    )
                except Exception:
                    async with async_session_maker() as db:
                        await db.execute(
                            update(Relationship)
                            .where(Relationship.user_id == user_id,
                                   Relationship.read_aware_special_used_count > 0)
                            .values(read_aware_special_used_count=(
                                Relationship.read_aware_special_used_count - 1)))
                        await db.commit()
                    raise
                logger.info("[已读IM] 特殊档入队 user=%s post=%s delay=%ss queue_id=%s prompt=P-14",
                            user_id, post_id, special_delay, qid)
                return
            logger.info("[已读IM] 特殊档并发占满，转常规档 user=%s", user_id)

        # 4. 常规档判定（P-08~P-11）
        prompt_key = _READ_REGULAR_PROMPT_KEY.get(stage, "prompt_p08")
        d_min, d_max = DEFAULT_READ_REGULAR_DELAY_SEC.get(stage, (1800, 7200))
        d_min = _to_int(
            await get_life_feed_config(read_regular_delay_key(stage, "min"), d_min), d_min)
        d_max = _to_int(
            await get_life_feed_config(read_regular_delay_key(stage, "max"), d_max), d_max)
        if d_max < d_min:
            d_max = d_min
        delay = random.randint(d_min, d_max)

        qid = await agent_aware_service.enqueue(
            user_id=user_id,
            aware_type=TriggerType.READ_AWARE,
            related_post_id=post_id,
            prompt_key=prompt_key,
            delay_seconds=delay,
            relationship_stage=stage,
            extra_context={"is_special": False},
        )
        logger.info("[已读IM] 常规档入队 user=%s post=%s 档位=%s prompt=%s delay=%ss queue_id=%s",
                    user_id, post_id, stage, prompt_key, delay, qid)

    async def generate_and_send(self, queue_row: AgentAwareQueue):
        """由 STEP-019 消费分派调用：生成已读感知文本（P-08~P-11/P-14 / LLM-07）。返回文本或 None。"""
        return await generate_aware_text(queue_row, node_key="llm_07", temperature=0.8)


# 全局单例
read_aware_service = ReadAwareService()
