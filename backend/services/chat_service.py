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
    schedule_debounced,
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


async def _max_assistant_sort_seq(session: AsyncSession, user_id: int, *, current=False) -> int | None:
    if current:
        return await session.scalar(select(ConversationLog.sort_seq).where(
            ConversationLog.user_id==user_id,ConversationLog.role=="assistant")
            .order_by(ConversationLog.sort_seq.desc()).limit(1).with_for_update())
    stmt = select(func.max(ConversationLog.sort_seq)).where(
        ConversationLog.user_id == user_id,
        ConversationLog.role == "assistant",
    )
    return (await session.execute(stmt)).scalar()


async def fetch_open_window_user_rows(session: AsyncSession, user_id: int, *, current=False) -> list[ConversationLog]:
    """最后一条 assistant 之后、尚未闭环的全部 user 行。"""
    max_a = await _max_assistant_sort_seq(session, user_id, current=current)
    q = select(ConversationLog).where(
        ConversationLog.user_id == user_id,
        ConversationLog.role == "user",
    )
    if max_a is not None:
        q = q.where(ConversationLog.sort_seq > max_a)
    q = q.order_by(ConversationLog.sort_seq.asc())
    if current:q=q.with_for_update().execution_options(populate_existing=True)
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


async def schedule_recovery_bundle(user_id, run_bundle):
    from backend.services.chat_lifecycle_runtime import scan_once
    await scan_once(run_bundle)


async def trigger_recovery_if_queue_stuck(user_id, db, run_bundle):
    # GETs are pure reads now. Startup/periodic SQL scanner owns recovery.
    return None


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
    """Retained symbol for isolation callers; generation requires SQL admission."""
    raise RuntimeError('generation_requires_atomic_admission')


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


async def await_bundle_payload(generation_id: str, user_id: int | None = None) -> dict[str, Any]:
    """Each observer owns its wait. SQL is authoritative after process/receipt loss."""
    if user_id is None:
        fut = await _get_or_create_bundle_future(generation_id)
        try:return await asyncio.wait_for(asyncio.shield(fut), timeout=BUNDLE_WAIT_TIMEOUT_SEC)
        except asyncio.TimeoutError:return {'error':True,'code':10110,'message':'结果待核实'}
    from datetime import datetime
    from backend.models.chat_lifecycle import ChatGeneration
    from backend.services import chat_lifecycle as life
    from backend.services.chat_timing import TIMING
    async with async_session_maker() as db:
        gen = (await db.execute(select(ChatGeneration).where(ChatGeneration.user_id==user_id,
            ChatGeneration.generation_id==generation_id))).scalar_one_or_none()
        if gen is None:return {'error':True,'code':10110}
        end=asyncio.get_running_loop().time()+max(0,(gen.deadline_at-datetime.utcnow()).total_seconds())+TIMING.server_wait_margin_ms/1000
    while True:
        payload=await life.generation_payload(user_id,generation_id)
        if payload is not None:return payload
        if asyncio.get_running_loop().time()>=end:return {'error':True,'code':10110,'message':'结果待核实'}
        await asyncio.sleep(.2)


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


async def submit(user_id, db, operation, request_id, run_bundle, *, content=None, channel='h5'):
    from backend.services import chat_lifecycle as life
    if request_id is not None:
        repeated = await life.duplicate(db,user_id,operation,request_id,content)
        await db.commit()  # release the read snapshot before slow input safety
        if repeated:return repeated
    safety = {}
    if operation == 'send':
        safety = await check_content_safety(content)
        if not safety['ok']:raise life.AdmissionError(safety['code'])
    admission = await life.admit(db,user_id,operation,request_id,content=safety.get('content'),
        persona_risk_flag=safety.get('persona_risk_flag',False),
        persona_risk_type=safety.get('persona_risk_type'),channel=channel)
    if not admission.repeated:
        from backend.services.chat_lifecycle_runtime import dispatch, admission_confirmed
        from backend.config import get_chat_debounce_ms
        admission_confirmed()
        # Outbox survives process exit before this local hint is registered.
        dispatch(user_id,admission.generation_id,run_bundle,
            max(1,get_chat_debounce_ms())/1000 if operation=='send' else 0)
    return admission


async def enqueue_send(user_id, db, content, persona_risk_flag, persona_risk_type, run_bundle,
                       request_id=None, channel='h5'):
    from backend.services import chat_lifecycle as life
    from backend.services.chat_lifecycle_runtime import dispatch, admission_confirmed
    from backend.config import get_chat_debounce_ms
    admission=await life.admit(db,user_id,'send',request_id,content=content,
        persona_risk_flag=persona_risk_flag,persona_risk_type=persona_risk_type,channel=channel)
    if not admission.repeated:
        admission_confirmed()
        dispatch(user_id,admission.generation_id,run_bundle,max(1,get_chat_debounce_ms())/1000)
    return admission.generation_id


async def enqueue_resend(user_id,db,run_bundle,request_id=None,channel='h5'):
    from backend.services.chat_lifecycle import AdmissionError
    try:
        admission=await submit(user_id,db,'resend',request_id,run_bundle,channel=channel)
        return admission.generation_id,None
    except AdmissionError as exc:return None,exc.code
