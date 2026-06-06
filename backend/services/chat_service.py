# -*- coding: utf-8 -*-
# 对话写路径：入队前校验、generation/Future、send/resend 入队与同步等待（H5 / Open 共用）

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_FAILED_ERROR,
    DELIVERY_STATUS_FAILED_TIMEOUT,
    DELIVERY_STATUS_PENDING_LLM,
    ERR_CONTENT_EMPTY,
    ERR_CONTENT_UNSAFE,
    ERR_LLM_FAILED,
    PERSONA_RISK_KEYWORDS,
)
from backend.database import async_session_maker
from backend.models.conversation_log import ConversationLog
from backend.models.relationship import Relationship
from backend.redis_client import get_redis
from backend.services.chat_queue_service import (
    redis_set_generation,
    release_bundle_lock,
    schedule_debounced,
    try_acquire_bundle_lock,
    try_consume_resend_quota,
)
from backend.services.content_safety_service import check_content
from backend.services.timeline_seq_service import allocate_sort_seq

logger = logging.getLogger(__name__)

# 与 H5 SSE 一致；Nginx proxy_read_timeout 须 ≥ 130s
BUNDLE_WAIT_TIMEOUT_SEC = 120.0

_generation_futures: dict[str, asyncio.Future] = {}
_generation_results: dict[str, dict[str, Any]] = {}
_gen_future_lock = asyncio.Lock()


# ============ 入队前共享校验（V9）============


def _detect_persona_risk(text: str) -> tuple[bool, str | None]:
    """人格风险关键词检测（与 routers.chat 历史逻辑一致）。"""
    text_lower = text.lower()
    for risk_type, keywords in PERSONA_RISK_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return True, risk_type
    return False, None


async def check_content_safety(content: str) -> dict[str, Any]:
    """
    内容安全 + 空内容 + persona_risk。
    返回 ok=True 时含 content / persona_risk_flag / persona_risk_type。
    """
    user_content = content.strip()
    if not user_content:
        return {"ok": False, "code": ERR_CONTENT_EMPTY}
    safety_result = await check_content(user_content)
    if not safety_result["is_safe"]:
        return {"ok": False, "code": ERR_CONTENT_UNSAFE}
    persona_risk_flag, persona_risk_type = _detect_persona_risk(user_content)
    return {
        "ok": True,
        "content": user_content,
        "persona_risk_flag": persona_risk_flag,
        "persona_risk_type": persona_risk_type,
    }


async def _max_assistant_sort_seq(session: AsyncSession, user_id: int) -> int | None:
    stmt = select(func.max(ConversationLog.sort_seq)).where(
        ConversationLog.user_id == user_id,
        ConversationLog.role == "assistant",
    )
    return (await session.execute(stmt)).scalar()


async def fetch_open_window_user_rows(session: AsyncSession, user_id: int) -> list[ConversationLog]:
    """最后一条 assistant 之后、尚未闭环的全部 user 行。"""
    max_a = await _max_assistant_sort_seq(session, user_id)
    q = select(ConversationLog).where(
        ConversationLog.user_id == user_id,
        ConversationLog.role == "user",
    )
    if max_a is not None:
        q = q.where(ConversationLog.sort_seq > max_a)
    q = q.order_by(ConversationLog.sort_seq.asc())
    return list((await session.execute(q)).scalars().all())


def open_window_has_bang(rows: list[ConversationLog]) -> bool:
    return any(
        r.delivery_status in (DELIVERY_STATUS_FAILED_TIMEOUT, DELIVERY_STATUS_FAILED_ERROR)
        for r in rows
    )


def _should_block_new_send(open_rows: list[ConversationLog]) -> bool:
    pending = [r for r in open_rows if r.delivery_status != DELIVERY_STATUS_DELIVERED]
    if len(pending) >= 5 and not open_window_has_bang(open_rows):
        return True
    return False


async def check_send_quota(user_id: int, db: AsyncSession) -> bool:
    """未闭环队列满时返回 True（应拒绝新 send）。"""
    open_rows = await fetch_open_window_user_rows(db, user_id)
    return _should_block_new_send(open_rows)


def _open_window_only_pending_llm(open_rows: list[ConversationLog]) -> bool:
    """未闭环行是否全部为 pending_llm（无叹号、易死锁）。"""
    pending = [r for r in open_rows if r.delivery_status != DELIVERY_STATUS_DELIVERED]
    if not pending:
        return False
    return all(r.delivery_status == DELIVERY_STATUS_PENDING_LLM for r in pending)


async def schedule_recovery_bundle(
    user_id: int,
    run_bundle: Callable[[int], Awaitable[None]],
) -> None:
    """队列卡死或 generation 作废后，后台补跑一轮打包（带 Redis 锁，避免并行双跑）。"""

    async def _guarded() -> None:
        if not await try_acquire_bundle_lock(user_id):
            return
        try:
            await run_bundle(user_id)
        finally:
            await release_bundle_lock(user_id)

    asyncio.create_task(_guarded())
    logger.info("已调度对话 bundle 恢复: user_id=%d", user_id)


async def trigger_recovery_if_queue_stuck(
    user_id: int,
    db: AsyncSession,
    run_bundle: Callable[[int], Awaitable[None]],
) -> None:
    """10104 前：若满队且全为 pending_llm，尝试触发恢复 bundle。"""
    open_rows = await fetch_open_window_user_rows(db, user_id)
    if _should_block_new_send(open_rows) and _open_window_only_pending_llm(open_rows):
        await schedule_recovery_bundle(user_id, run_bundle)


# ============ generation + Future ============


async def _invalidate_generation_future(old_gen: str | None) -> None:
    if not old_gen:
        return
    async with _gen_future_lock:
        _generation_results.pop(old_gen, None)
        fut = _generation_futures.pop(old_gen, None)
    if fut is not None and not fut.done():
        fut.set_result({"obsolete": True})


async def new_generation_for_user(user_id: int) -> str:
    r = await get_redis()
    key = f"chat:gen:{user_id}"
    old = await r.get(key)
    new_gen = str(uuid.uuid4())
    await redis_set_generation(user_id, new_gen)
    await _invalidate_generation_future(old)
    return new_gen


async def _get_or_create_bundle_future(gen: str) -> asyncio.Future:
    loop = asyncio.get_running_loop()
    async with _gen_future_lock:
        cached = _generation_results.pop(gen, None)
        if cached is not None:
            fut_done: asyncio.Future = loop.create_future()
            fut_done.set_result(cached)
            return fut_done
        fut = _generation_futures.get(gen)
        if fut is None:
            fut = loop.create_future()
            _generation_futures[gen] = fut
        return fut


async def resolve_generation_future(gen: str, payload: dict[str, Any]) -> None:
    """供 routers.chat._execute_llm_bundle 唤醒等待方。"""
    async with _gen_future_lock:
        fut = _generation_futures.get(gen)
        if fut is not None and not fut.done():
            fut.set_result(payload)
            return
        _generation_results[gen] = payload


async def await_bundle_payload(generation_id: str) -> dict[str, Any]:
    """asyncio 等待 bundle 结果（O2）；清理 Future 注册。"""
    fut = await _get_or_create_bundle_future(generation_id)
    try:
        return await asyncio.wait_for(fut, timeout=BUNDLE_WAIT_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        return {"error": True, "code": ERR_LLM_FAILED, "message": "等待回复超时"}
    finally:
        async with _gen_future_lock:
            _generation_futures.pop(generation_id, None)
            _generation_results.pop(generation_id, None)


def build_done_messages_from_payload(payload: dict[str, Any]) -> tuple[list[dict], dict, str | None]:
    """从 Future payload 提取 V3 / SSE done 同源字段。"""
    step5_data = payload.get("step5") or {}
    messages_raw = step5_data.get("messages") or []
    emotion_data = payload.get("emotion") or {"label": "平静", "confidence": 1.0}
    if not messages_raw:
        reply = payload.get("reply") or ""
        messages_raw = [{"type": "text", "content": reply}] if reply else []
    done_messages = [
        {"type": m.get("type", "text"), "content": m.get("content", "")} for m in messages_raw
    ]
    round_id = payload.get("round_id")
    return done_messages, emotion_data, round_id


# ============ 入队 ============


async def _reset_proactive_times(user_id: int) -> None:
    try:
        async with async_session_maker() as _reset_db:
            _rel_stmt = select(Relationship).where(Relationship.user_id == user_id)
            _rel_result = await _reset_db.execute(_rel_stmt)
            _rel = _rel_result.scalar_one_or_none()
            if _rel is not None and _rel.proactive_times != 0:
                _rel.proactive_times = 0
                await _reset_db.commit()
                logger.info("proactive_times 清零: user_id=%d", user_id)
    except Exception:
        logger.exception("proactive_times 清零失败: user_id=%d", user_id)


async def enqueue_send(
    user_id: int,
    db: AsyncSession,
    content: str,
    persona_risk_flag: bool,
    persona_risk_type: str | None,
    run_bundle: Callable[[int], Awaitable[None]],
) -> str:
    """写入 user 行并防抖调度 bundle；返回 generation_id。"""
    generation_id = await new_generation_for_user(user_id)
    await _get_or_create_bundle_future(generation_id)

    seqs = await allocate_sort_seq(user_id, count=1, db=db)
    user_log = ConversationLog(
        user_id=user_id,
        role="user",
        content=content,
        memory_injected=None,
        persona_risk_flag=persona_risk_flag,
        persona_risk_type=persona_risk_type,
        sort_seq=seqs[0],
        delivery_status=DELIVERY_STATUS_PENDING_LLM,
        skipped_in_prompt=False,
    )
    db.add(user_log)
    await db.commit()

    await _reset_proactive_times(user_id)

    async def _debounced_run() -> None:
        await run_bundle(user_id)

    await schedule_debounced(user_id, _debounced_run)
    return generation_id


async def enqueue_resend(
    user_id: int,
    db: AsyncSession,
    run_bundle: Callable[[int], Awaitable[None]],
) -> tuple[str | None, int | None]:
    """
    叹号重发入队。成功返回 (generation_id, None)；失败返回 (None, error_code)。
    """
    from backend.constants import ERR_CHAT_NOTHING_TO_RESEND, ERR_CHAT_RESEND_LIMIT

    open_rows = await fetch_open_window_user_rows(db, user_id)
    if not open_window_has_bang(open_rows):
        return None, ERR_CHAT_NOTHING_TO_RESEND

    batch_key = str(min(r.sort_seq for r in open_rows))
    if not await try_consume_resend_quota(user_id, batch_key):
        return None, ERR_CHAT_RESEND_LIMIT

    generation_id = await new_generation_for_user(user_id)
    await _get_or_create_bundle_future(generation_id)
    asyncio.create_task(run_bundle(user_id))
    return generation_id, None
