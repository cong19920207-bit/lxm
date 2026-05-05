# -*- coding: utf-8 -*-
# Future 槽消费轮询 Handler：扫描到期 Future 槽，执行消费并触发主动消息子链路

import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_maker
from backend.models.agent_message import TriggerType
from backend.models.relationship import Relationship
from backend.models.user import User
from backend.redis_client import get_redis
from backend.services.agent_service import agent_service
from backend.services.step8_subchain import execute_step8_subchain

logger = logging.getLogger(__name__)

# Future 槽有效窗口：到期后 30 分钟内仍可消费
FUTURE_EXPIRE_WINDOW_SECONDS = 1800


class FutureSlotHandler:
    """
    独立后台轮询：消费到期的 Future 槽。

    消费 4 个条件（同时满足）：
    ① future_timestamp 不为空
    ② future_timestamp ≤ 当前时间（已到期）
    ③ future_timestamp > 当前时间 - 1800（30 分钟窗口内）
    ④ 用户未封禁

    通过检查后执行：
    - 黑名单检查 + 行动评分 ≥ 6（绕过 8 次/天 + 30min 间隔频控）
    - 检查通过 → 触发 Step8 子链路（STEP-024 实现，当前为占位）
    - 消费成功 → 清空 Future 槽 + proactive_times +1 + 计入 agent:count
    - 检查不通过 → 清空槽位 + 写日志
    """

    async def scan_and_consume(self) -> int:
        """
        扫描全部到期 Future 槽并逐一消费。

        Returns:
            本轮消费成功的数量
        """
        consumed = 0
        now_ts = int(time.time())
        window_start = now_ts - FUTURE_EXPIRE_WINDOW_SECONDS

        try:
            async with async_session_maker() as db:
                # 联表查询：relationship 有到期 Future 且 user 未封禁
                stmt = (
                    select(Relationship)
                    .join(User, Relationship.user_id == User.id)
                    .where(
                        and_(
                            Relationship.future_timestamp.isnot(None),
                            Relationship.future_timestamp <= now_ts,
                            Relationship.future_timestamp > window_start,
                            User.is_banned == False,  # noqa: E712
                        )
                    )
                )
                result = await db.execute(stmt)
                candidates = list(result.scalars().all())

            if not candidates:
                return 0

            logger.info("[FutureHandler] 发现 %d 个到期 Future 槽", len(candidates))

            for rel in candidates:
                try:
                    success = await self._consume_one(rel.user_id, rel.future_action)
                    if success:
                        consumed += 1
                except Exception:
                    logger.exception(
                        "[FutureHandler] 消费 user_id=%d 异常", rel.user_id
                    )

        except Exception:
            logger.exception("[FutureHandler] scan_and_consume 异常")

        if consumed > 0:
            logger.info("[FutureHandler] 本轮消费成功 %d 个", consumed)
        return consumed

    async def _consume_one(self, user_id: int, future_action: str | None) -> bool:
        """
        消费单个用户的 Future 槽。

        Returns:
            True=触发成功, False=检查不通过或失败
        """
        r = await get_redis()

        # ── 黑名单检查 ──
        blacklist_key = f"agent:blacklist:{user_id}"
        is_blacklisted = await r.exists(blacklist_key)
        if is_blacklisted:
            logger.info(
                "[FutureHandler] user_id=%d 在黑名单中，清空 Future 槽", user_id
            )
            await self._clear_future_slot(user_id)
            return False

        # ── 行动评分检查（复用 agent_service，trigger_type=FUTURE）──
        score = await agent_service.calculate_action_score(
            user_id, TriggerType.FUTURE
        )
        if score < 6:
            logger.info(
                "[FutureHandler] user_id=%d 行动评分 %.1f < 6，清空 Future 槽",
                user_id, score,
            )
            await self._clear_future_slot(user_id)
            return False

        # ── 检查通过，触发 Step8 子链路 ──
        logger.info(
            "[FutureHandler] user_id=%d 通过检查(score=%.1f)，触发 Step8 子链路, action=%s",
            user_id, score, future_action,
        )

        # STEP-024：调用 Step8 子链路（复用主链 Step 变体）
        trigger_success = await execute_step8_subchain(user_id, future_action)

        if trigger_success:
            # 消费成功后的收尾操作
            await self._on_consume_success(user_id)
            logger.info("[FutureHandler] user_id=%d Future 槽消费成功", user_id)
        else:
            # 消息生成失败也清空槽位，避免反复重试
            await self._clear_future_slot(user_id)
            logger.warning(
                "[FutureHandler] user_id=%d 消息生成失败，清空 Future 槽", user_id
            )

        return trigger_success

    async def _on_consume_success(self, user_id: int) -> None:
        """
        消费成功后：
        1. 清空 Future 槽
        2. proactive_times +1（上限 3）
        3. 计入 agent:count 计数器（R-AGT-02）
        """
        try:
            async with async_session_maker() as db:
                stmt = select(Relationship).where(Relationship.user_id == user_id)
                result = await db.execute(stmt)
                rel = result.scalar_one_or_none()
                if rel is not None:
                    # 清空 Future 槽
                    rel.future_timestamp = None
                    rel.future_action = None
                    # proactive_times +1（上限 3）
                    if rel.proactive_times < 3:
                        rel.proactive_times += 1
                    await db.commit()
        except Exception:
            logger.exception(
                "[FutureHandler] 清空槽位/更新 proactive_times 失败: user_id=%d",
                user_id,
            )

        # 计入 agent:count 频控计数器（绕过频控但须计入）
        await agent_service.increment_agent_count_for_future(user_id)

    async def _clear_future_slot(self, user_id: int) -> None:
        """仅清空 Future 槽（检查不通过时调用）"""
        try:
            async with async_session_maker() as db:
                stmt = select(Relationship).where(Relationship.user_id == user_id)
                result = await db.execute(stmt)
                rel = result.scalar_one_or_none()
                if rel is not None:
                    rel.future_timestamp = None
                    rel.future_action = None
                    await db.commit()
        except Exception:
            logger.exception(
                "[FutureHandler] 清空 Future 槽失败: user_id=%d", user_id
            )

    async def cleanup_expired_slots(self) -> int:
        """
        清理过期超过 30 分钟窗口的 Future 槽（防止脏数据残留）。

        Returns:
            清理的数量
        """
        cleaned = 0
        window_start = int(time.time()) - FUTURE_EXPIRE_WINDOW_SECONDS
        try:
            async with async_session_maker() as db:
                stmt = select(Relationship).where(
                    and_(
                        Relationship.future_timestamp.isnot(None),
                        Relationship.future_timestamp <= window_start,
                    )
                )
                result = await db.execute(stmt)
                expired = list(result.scalars().all())

                for rel in expired:
                    rel.future_timestamp = None
                    rel.future_action = None
                    cleaned += 1
                    logger.info(
                        "[FutureHandler] 清理过期 Future 槽: user_id=%d, ts=%d",
                        rel.user_id, rel.future_timestamp or 0,
                    )

                if cleaned > 0:
                    await db.commit()
                    logger.info("[FutureHandler] 清理过期 Future 槽完成，共 %d 个", cleaned)
        except Exception:
            logger.exception("[FutureHandler] cleanup_expired_slots 异常")

        return cleaned


# 全局单例
future_handler = FutureSlotHandler()
