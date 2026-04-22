# -*- coding: utf-8 -*-
# 内容安全检测服务：基于 Redis 违规关键词列表

import asyncio
import datetime
import json
import logging

from backend.redis_client import get_redis

logger = logging.getLogger(__name__)

# Redis 存储违规关键词列表的 key
BANNED_KEYWORDS_KEY = "banned_keywords"


async def check_content(text: str) -> dict:
    """
    检查文本是否命中违规关键词。

    违规关键词列表从 Redis 读取（key=banned_keywords，JSON 数组格式）。

    Args:
        text: 待检查的文本

    Returns:
        {"is_safe": True/False, "reason": "命中违规词: xxx" 或 ""}
    """
    if not text or not text.strip():
        return {"is_safe": True, "reason": ""}

    try:
        r = await get_redis()
        raw = await r.get(BANNED_KEYWORDS_KEY)

        if not raw:
            return {"is_safe": True, "reason": ""}

        try:
            keywords = json.loads(raw)
        except json.JSONDecodeError:
            # 兼容逗号分隔的纯文本格式
            keywords = [w.strip() for w in raw.split(",") if w.strip()]

        if not keywords:
            return {"is_safe": True, "reason": ""}

        text_lower = text.lower()
        for keyword in keywords:
            if not keyword:
                continue
            if keyword.lower() in text_lower:
                logger.warning("内容安全检测命中违规词: %s", keyword)
                asyncio.create_task(_record_block())
                return {
                    "is_safe": False,
                    "reason": f"命中违规词: {keyword}",
                }

        return {"is_safe": True, "reason": ""}

    except Exception as e:
        logger.error("内容安全检测异常: %s", str(e))
        # 检测异常时默认放行，避免误拦截
        return {"is_safe": True, "reason": ""}


async def _record_block():
    """异步写入内容拦截计数到 Redis"""
    today = datetime.date.today().strftime("%Y%m%d")
    try:
        r = await get_redis()
        await r.incr(f"content_block_count:{today}")
        await r.expire(f"content_block_count:{today}", 172800)
    except Exception:
        pass
