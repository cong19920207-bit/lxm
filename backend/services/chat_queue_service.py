# -*- coding: utf-8 -*-
# TD-015：对话队列 Redis 侧 — generation、防抖计时、叹号重发限流（多实例安全依赖 Redis 校验）

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from backend.config import get_chat_debounce_ms
from backend.redis_client import get_redis

logger = logging.getLogger(__name__)

REDIS_GEN_KEY = "chat:gen:{user_id}"
REDIS_DEBOUNCE_TOKEN_KEY = "chat:debounce_tok:{user_id}"
REDIS_RESEND_KEY = "chat:resend:{user_id}:{batch_key}"

GEN_TTL_SEC = 86400 * 7

# 本地防抖任务：仅用于取消「同进程」内重复 sleep；跨实例以 Redis token 为准
_debounce_tasks: dict[int, asyncio.Task] = {}


def cancel_local_debounce_task(user_id: int) -> None:
    t = _debounce_tasks.pop(user_id, None)
    if t is not None and not t.done():
        t.cancel()


async def redis_get_generation(user_id: int) -> str | None:
    r = await get_redis()
    return await r.get(REDIS_GEN_KEY.format(user_id=user_id))


async def redis_set_generation(user_id: int, gen: str) -> None:
    r = await get_redis()
    await r.set(REDIS_GEN_KEY.format(user_id=user_id), gen, ex=GEN_TTL_SEC)


async def redis_bump_generation(user_id: int) -> str:
    """换新代并写入 Redis；调用方负责作废本代对应的 Future（见 chat 路由模块）。"""
    new_gen = str(uuid.uuid4())
    await redis_set_generation(user_id, new_gen)
    return new_gen


async def schedule_debounced(
    user_id: int,
    coro: Callable[[], Awaitable[None]],
) -> None:
    """
    防抖：每次入队刷新 token；delay_ms 后仅 token 仍匹配的那次执行 coro。
    多实例下多个 worker 可能同时醒来，仅 token 与 Redis 一致者执行。
    """
    delay_ms = max(1, int(get_chat_debounce_ms()))
    token = str(uuid.uuid4())
    r = await get_redis()
    tok_key = REDIS_DEBOUNCE_TOKEN_KEY.format(user_id=user_id)
    # TTL 略长于防抖，避免 key 过早消失导致误判
    await r.set(tok_key, token, px=delay_ms + 15000)

    async def _runner() -> None:
        try:
            await asyncio.sleep(delay_ms / 1000.0)
            cur = await r.get(tok_key)
            if cur != token:
                return
            await coro()
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("防抖调度执行失败 user_id=%s", user_id)

    cancel_local_debounce_task(user_id)
    t = asyncio.create_task(_runner())
    _debounce_tasks[user_id] = t


async def try_consume_resend_quota(
    user_id: int,
    batch_key: str,
    *,
    max_per_window: int = 2,
    window_sec: int = 60,
) -> bool:
    """
    叹号重发限流：每用户每 batch_key 每 window_sec 秒最多 max_per_window 次。
    返回 True 表示允许本次重发；False 表示超限。
    """
    r = await get_redis()
    k = REDIS_RESEND_KEY.format(user_id=user_id, batch_key=batch_key)
    n = await r.incr(k)
    if n == 1:
        await r.expire(k, window_sec)
    if int(n) > max_per_window:
        return False
    return True
