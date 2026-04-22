# -*- coding: utf-8 -*-
"""
TD-020 / V3-A：用户短期情绪属性 — Redis 热层 + DB 冷层。

读写矩阵（与 tech-debt [TD-020]、contract 一致）：
- **写**：`chat._post_bundle_success_tasks` 在每轮成功闭环后调用 `persist_after_round`；
  Redis `user_emotion:{user_id}`（TTL=`get_redis_user_emotion_ttl_seconds()` / 环境变量 `REDIS_USER_EMOTION_TTL`）
  与表 `user_short_term_emotion` 同行 upsert（TTL 到期前已持久化）。
- **读**：仅 `chat._execute_llm_bundle` 调用 `read_for_prompt`；顺序 Redis → DB 表 → `emotion_log` 最新一条。
- **与 ai_emotion 关系**：`ai_emotion:{user_id}` 仍为关系页等「展示态」JSON（本轮 LLM emotion），TTL 86400 现网不变；
  `user_emotion:*` 专供 Prompt 侧「短期属性」真相源，二者键名与语义分离。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_redis_user_emotion_ttl_seconds
from backend.database import async_session_maker
from backend.models.emotion_log import EmotionLog
from backend.models.user_short_term_emotion import UserShortTermEmotion

logger = logging.getLogger(__name__)


def build_redis_key(user_id: int) -> str:
    """Redis 键：`user_emotion:{user_id}`。"""
    return f"user_emotion:{user_id}"


def _parse_emotion_payload(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    label = data.get("label")
    if not label or not isinstance(label, str):
        return None
    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    return {"label": label, "confidence": conf}


async def _fallback_latest_emotion_log(user_id: int, db: AsyncSession) -> dict | None:
    """与改前 `_get_latest_emotion` 一致：emotion_log 最新一条（轮级审计）。"""
    stmt = (
        select(EmotionLog)
        .where(EmotionLog.user_id == user_id)
        .order_by(desc(EmotionLog.created_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    emotion = result.scalar_one_or_none()
    if emotion:
        return {"label": emotion.emotion_label, "confidence": emotion.confidence}
    return None


async def read_for_prompt(user_id: int, db: AsyncSession, redis_client: Any) -> dict | None:
    """
    供打包 LLM 注入 Prompt 的情绪上下文（短期属性优先）。
    禁止在 `POST /api/chat/send` 首段调用本函数所需的 Redis 逻辑外扩；调用方仅限 `_execute_llm_bundle`。
    """
    try:
        raw = await redis_client.get(build_redis_key(user_id))
    except Exception:
        logger.exception("读取用户短期情绪 Redis 失败 user_id=%s", user_id)
        raw = None

    parsed = _parse_emotion_payload(raw) if raw else None
    if parsed:
        return parsed

    try:
        stmt = select(UserShortTermEmotion).where(UserShortTermEmotion.user_id == user_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return {"label": row.emotion_label, "confidence": row.confidence}
    except Exception:
        logger.exception("读取用户短期情绪 DB 失败 user_id=%s", user_id)

    return await _fallback_latest_emotion_log(user_id, db)


async def persist_after_round(user_id: int, emotion_data: dict, redis_client: Any) -> None:
    """
    每轮成功闭环后置：刷新 Redis TTL，并 upsert DB（与 Redis 同快照，避免键过期后无画像）。
    emotion_data：与 LLM 结构化输出一致，至少含 label、confidence。
    """
    label = str(emotion_data.get("label", "平静") or "平静")
    try:
        confidence = float(emotion_data.get("confidence", 1.0))
    except (TypeError, ValueError):
        confidence = 1.0

    ttl = get_redis_user_emotion_ttl_seconds()
    cache_body = json.dumps({"label": label, "confidence": confidence}, ensure_ascii=False)
    key = build_redis_key(user_id)

    try:
        await redis_client.set(key, cache_body, ex=ttl)
    except Exception:
        logger.exception("写入用户短期情绪 Redis 失败 user_id=%s", user_id)

    payload_str = json.dumps(emotion_data, ensure_ascii=False)
    now = datetime.utcnow()

    try:
        async with async_session_maker() as session:
            stmt = select(UserShortTermEmotion).where(UserShortTermEmotion.user_id == user_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                row.emotion_label = label
                row.confidence = confidence
                row.payload = payload_str
                row.updated_at = now
            else:
                session.add(
                    UserShortTermEmotion(
                        user_id=user_id,
                        emotion_label=label,
                        confidence=confidence,
                        payload=payload_str,
                        updated_at=now,
                    )
                )
            await session.commit()
    except Exception:
        logger.exception("写入用户短期情绪 DB 失败 user_id=%s", user_id)
