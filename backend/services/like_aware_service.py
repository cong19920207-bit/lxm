# -*- coding: utf-8 -*-
# 生活流·点赞感知 IM 服务（LLM-06 · STEP-020）
#
# PRD 6.1.3 点赞 IM 完整规则：
#   - 同帖 LIKE_AWARE 去重（pending/generating/sent 任一存在即跳过）
#   - 特殊档（注册窗口内 + 次数未满）：100% 触发，延迟 like_aware_special_delay_sec，
#     relationship.like_aware_special_used_count 原子 +1，Prompt=P-07
#   - 常规档：random<0.30 才入队，延迟按关系档 like_regular_delay_{stage}_{min,max}，Prompt=P-07
# on_like_hook 由 STEP-016 点赞 API 调用（签名与 M1 stub 保持一致）；
# generate_and_send 由 STEP-019 消费分派调用。

import logging
import random
from datetime import datetime, timedelta

from sqlalchemy import select, update

from backend.constants.life_feed_config import (
    CONFIG_LIKE_AWARE_SPECIAL_DELAY_SEC,
    CONFIG_LIKE_AWARE_SPECIAL_MAX_COUNT,
    CONFIG_LIKE_AWARE_SPECIAL_WINDOW_HOURS,
    DEFAULT_LIKE_AWARE_SPECIAL_DELAY_SEC,
    DEFAULT_LIKE_AWARE_SPECIAL_MAX_COUNT,
    DEFAULT_LIKE_AWARE_SPECIAL_WINDOW_HOURS,
    DEFAULT_LIKE_REGULAR_DELAY_SEC,
    level_to_stage,
    like_regular_delay_key,
)
from backend.database import async_session_maker
from backend.models.agent_aware_queue import AgentAwareQueue
from backend.models.agent_message import TriggerType
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.services.agent_aware_service import agent_aware_service, generate_aware_text
from backend.services.life_feed_config_service import get_life_feed_config

logger = logging.getLogger(__name__)

_LIKE_REGULAR_PROBABILITY = 0.30
_LIKE_PROMPT_KEY = "prompt_p07"


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class LikeAwareService:
    """点赞感知 IM（LLM-06）"""

    async def on_like_hook(self, user_id: int, post_id: int) -> None:
        """
        点赞感知钩子（STEP-016 点赞成功后调用）。
        判定同帖去重 → 特殊档 → 常规档 30%，命中则入队 agent_aware_queue。
        入队判定异常一律吞掉并记日志，保证不影响点赞主流程。
        """
        try:
            await self._process(user_id, post_id)
        except Exception as e:
            logger.error("[点赞IM] on_like_hook 异常（不影响点赞）user=%s post=%s: %s",
                         user_id, post_id, e, exc_info=True)

    async def _process(self, user_id: int, post_id: int) -> None:
        # 1. 同帖 LIKE_AWARE 去重
        async with async_session_maker() as db:
            exists = (await db.execute(
                select(AgentAwareQueue.id).where(
                    AgentAwareQueue.user_id == user_id,
                    AgentAwareQueue.post_id == post_id,
                    AgentAwareQueue.trigger_type == TriggerType.LIKE_AWARE,
                    AgentAwareQueue.status.in_(["pending", "generating", "sent"]),
                ).limit(1)
            )).scalars().first()
        if exists:
            logger.info("[点赞IM] 跳过 user=%s post=%s reason=already_queued", user_id, post_id)
            return

        # 载入用户 + 关系
        async with async_session_maker() as db:
            user = (await db.execute(
                select(User).where(User.id == user_id))).scalars().first()
            rel = (await db.execute(
                select(Relationship).where(Relationship.user_id == user_id))).scalars().first()
        if user is None:
            logger.warning("[点赞IM] 用户不存在，跳过 user=%s", user_id)
            return

        level = int(rel.level) if rel and rel.level is not None else 0
        stage = level_to_stage(level)

        # 读配置
        window_hours = _to_int(
            await get_life_feed_config(CONFIG_LIKE_AWARE_SPECIAL_WINDOW_HOURS,
                                       DEFAULT_LIKE_AWARE_SPECIAL_WINDOW_HOURS),
            DEFAULT_LIKE_AWARE_SPECIAL_WINDOW_HOURS)
        special_max = _to_int(
            await get_life_feed_config(CONFIG_LIKE_AWARE_SPECIAL_MAX_COUNT,
                                       DEFAULT_LIKE_AWARE_SPECIAL_MAX_COUNT),
            DEFAULT_LIKE_AWARE_SPECIAL_MAX_COUNT)
        special_delay = _to_int(
            await get_life_feed_config(CONFIG_LIKE_AWARE_SPECIAL_DELAY_SEC,
                                       DEFAULT_LIKE_AWARE_SPECIAL_DELAY_SEC),
            DEFAULT_LIKE_AWARE_SPECIAL_DELAY_SEC)

        used_count = int(rel.like_aware_special_used_count) if rel else 0
        within_window = (
            user.created_at is not None
            and datetime.utcnow() - user.created_at <= timedelta(hours=window_hours)
        )

        # 2. 特殊档判定（PRD 6.1.3：入队成功才消耗次数；并发用 CAS 占位，入队失败回滚）
        if within_window and used_count < special_max and rel is not None:
            async with async_session_maker() as db:
                res = await db.execute(
                    update(Relationship)
                    .where(Relationship.user_id == user_id,
                           Relationship.like_aware_special_used_count < special_max)
                    .values(like_aware_special_used_count=Relationship.like_aware_special_used_count + 1))
                await db.commit()
            if res.rowcount and res.rowcount == 1:
                try:
                    qid = await agent_aware_service.enqueue(
                        user_id=user_id,
                        aware_type=TriggerType.LIKE_AWARE,
                        related_post_id=post_id,
                        prompt_key=_LIKE_PROMPT_KEY,
                        delay_seconds=special_delay,
                        relationship_stage=stage,
                        extra_context={"is_special": True},
                    )
                except Exception:
                    # 入队失败：回滚占位，避免空耗特殊档次数
                    async with async_session_maker() as db:
                        await db.execute(
                            update(Relationship)
                            .where(Relationship.user_id == user_id,
                                   Relationship.like_aware_special_used_count > 0)
                            .values(like_aware_special_used_count=(
                                Relationship.like_aware_special_used_count - 1)))
                        await db.commit()
                    raise
                logger.info("[点赞IM] 特殊档入队 user=%s post=%s delay=%ss queue_id=%s",
                            user_id, post_id, special_delay, qid)
                return
            # 并发下已被占满 → 落常规档
            logger.info("[点赞IM] 特殊档并发占满，转常规档 user=%s", user_id)

        # 3. 常规档判定：30% 命中
        roll = random.random()
        if roll >= _LIKE_REGULAR_PROBABILITY:
            logger.info("[点赞IM] 跳过 user=%s post=%s reason=30%%_miss roll=%.3f",
                        user_id, post_id, roll)
            return

        d_min, d_max = DEFAULT_LIKE_REGULAR_DELAY_SEC.get(stage, (3600, 7200))
        d_min = _to_int(
            await get_life_feed_config(like_regular_delay_key(stage, "min"), d_min), d_min)
        d_max = _to_int(
            await get_life_feed_config(like_regular_delay_key(stage, "max"), d_max), d_max)
        if d_max < d_min:
            d_max = d_min
        delay = random.randint(d_min, d_max)

        qid = await agent_aware_service.enqueue(
            user_id=user_id,
            aware_type=TriggerType.LIKE_AWARE,
            related_post_id=post_id,
            prompt_key=_LIKE_PROMPT_KEY,
            delay_seconds=delay,
            relationship_stage=stage,
            extra_context={"is_special": False},
        )
        logger.info("[点赞IM] 常规档入队 user=%s post=%s 档位=%s delay=%ss queue_id=%s",
                    user_id, post_id, stage, delay, qid)

    async def generate_and_send(self, queue_row: AgentAwareQueue):
        """由 STEP-019 消费分派调用：生成点赞感知文本（P-07 / LLM-06）。返回文本或 None。"""
        return await generate_aware_text(queue_row, node_key="llm_06", temperature=0.7)


# 全局单例
like_aware_service = LikeAwareService()


async def on_like_hook(user_id: int, post_id: int) -> None:
    """模块级兼容入口（STEP-016 通过 like_aware_service.on_like_hook 调用；保留旧函数签名）。"""
    await like_aware_service.on_like_hook(user_id, post_id)
