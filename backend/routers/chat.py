# -*- coding: utf-8 -*-
# 对话相关 API：TD-015 入队即落库、generation、防抖调度、打包 LLM、叹号重发、SSE meta

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_llm_timeout_chat_seconds
from backend.constants import (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_FAILED_ERROR,
    DELIVERY_STATUS_FAILED_TIMEOUT,
    DELIVERY_STATUS_PENDING_LLM,
    ERR_CHAT_NOTHING_TO_RESEND,
    ERR_CHAT_QUEUE_FULL,
    ERR_CHAT_RESEND_LIMIT,
    ERR_CONTENT_EMPTY,
    ERR_CONTENT_UNSAFE,
    ERR_LLM_FAILED,
    PERSONA_RISK_KEYWORDS,
)
from backend.database import async_session_maker, get_db
from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.models.relationship import Relationship
from backend.redis_client import get_redis
from backend.schemas.chat import ChatResendRequest, ChatSendRequest
from backend.schemas.common import ApiResponse
from backend.services.chat_queue_service import (
    cancel_local_debounce_task,
    redis_get_generation,
    redis_set_generation,
    schedule_debounced,
    try_consume_resend_quota,
)
from backend.services.content_safety_service import check_content
from backend.services.embedding_service import embedding_service
from backend.services.llm_service import llm_service
from backend.services.memory_service import memory_service
from backend.services.prompt_builder import PromptBuilder
from backend.services.relationship_service import RelationshipService
from backend.services import user_short_term_emotion_service
from backend.services.timeline_seq_service import allocate_sort_seq
from backend.utils.auth_middleware import get_current_user
from backend.utils.dashvector_client import dashvector_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["对话"])

_SSE_CHUNK_SIZE = 2
_SSE_CHUNK_DELAY = 0.03

# 每代 SSE 等待 LLM 闭环结果；与 LLM_TIMEOUT_CHAT 对齐并留余量
_BUNDLE_WAIT_TIMEOUT_SEC = 55.0

# generation_id -> Future，供 SSE 与打包任务对接
_generation_futures: dict[str, asyncio.Future] = {}
# Worker 早于 SSE await 完成时暂存结果，避免客户端永远等不到
_generation_results: dict[str, dict[str, Any]] = {}
_gen_future_lock = asyncio.Lock()


# ============ 数据读取（独立 session 防 gather 冲突）============


async def _get_recent_conversations(
    user_id: int, db: AsyncSession | None = None, limit: int = 20
) -> list[ConversationLog]:
    async def _fetch(session: AsyncSession) -> list[ConversationLog]:
        stmt = (
            select(ConversationLog)
            .where(ConversationLog.user_id == user_id)
            .order_by(desc(ConversationLog.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    if db is not None:
        return await _fetch(db)
    async with async_session_maker() as session:
        return await _fetch(session)


async def _get_relationship(user_id: int, db: AsyncSession | None = None) -> Relationship | None:
    async def _fetch(session: AsyncSession) -> Relationship | None:
        stmt = select(Relationship).where(Relationship.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    if db is not None:
        return await _fetch(db)
    async with async_session_maker() as session:
        return await _fetch(session)


async def _get_latest_emotion(user_id: int, db: AsyncSession | None = None) -> dict | None:
    async def _fetch(session: AsyncSession) -> dict | None:
        stmt = (
            select(EmotionLog)
            .where(EmotionLog.user_id == user_id)
            .order_by(desc(EmotionLog.created_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        emotion = result.scalar_one_or_none()
        if emotion:
            return {"label": emotion.emotion_label, "confidence": emotion.confidence}
        return None

    if db is not None:
        return await _fetch(db)
    async with async_session_maker() as session:
        return await _fetch(session)


async def _get_embedding(text: str) -> list[float]:
    return await embedding_service.get_embedding(text)


async def _search_memories(vector: list[float], user_id: int) -> list[dict]:
    return await dashvector_client.search(
        vector=vector,
        user_id=user_id,
        top_k=5,
        threshold=0.7,
    )


def _detect_persona_risk(text: str) -> tuple[bool, str | None]:
    text_lower = text.lower()
    for risk_type, keywords in PERSONA_RISK_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return True, risk_type
    return False, None


# ============ 未闭环窗口 / 队列 ============


async def _max_assistant_sort_seq(session: AsyncSession, user_id: int) -> int | None:
    stmt = select(func.max(ConversationLog.sort_seq)).where(
        ConversationLog.user_id == user_id,
        ConversationLog.role == "assistant",
    )
    return (await session.execute(stmt)).scalar()


async def _fetch_open_window_user_rows(session: AsyncSession, user_id: int) -> list[ConversationLog]:
    """最后一条 assistant 之后、尚未闭环的全部 user 行（按 sort_seq 升序）。"""
    max_a = await _max_assistant_sort_seq(session, user_id)
    q = select(ConversationLog).where(
        ConversationLog.user_id == user_id,
        ConversationLog.role == "user",
    )
    if max_a is not None:
        q = q.where(ConversationLog.sort_seq > max_a)
    q = q.order_by(ConversationLog.sort_seq.asc())
    return list((await session.execute(q)).scalars().all())


def _open_window_has_bang(rows: list[ConversationLog]) -> bool:
    return any(
        r.delivery_status in (DELIVERY_STATUS_FAILED_TIMEOUT, DELIVERY_STATUS_FAILED_ERROR)
        for r in rows
    )


def _should_block_new_send(open_rows: list[ConversationLog]) -> bool:
    """无叹号时未处理 user 行 ≥5 则拒绝新入队。"""
    pending = [
        r
        for r in open_rows
        if r.delivery_status != DELIVERY_STATUS_DELIVERED
    ]
    if len(pending) >= 5 and not _open_window_has_bang(open_rows):
        return True
    return False


# ============ generation + Future ============


async def _invalidate_generation_future(old_gen: str | None) -> None:
    if not old_gen:
        return
    async with _gen_future_lock:
        _generation_results.pop(old_gen, None)
        fut = _generation_futures.pop(old_gen, None)
    if fut is not None and not fut.done():
        fut.set_result({"obsolete": True})


async def _new_generation_for_user(user_id: int) -> str:
    """换新代并作废旧代 Future。"""
    r = await get_redis()
    key = f"chat:gen:{user_id}"
    old = await r.get(key)
    new_gen = str(uuid.uuid4())
    await redis_set_generation(user_id, new_gen)
    await _invalidate_generation_future(old)
    return new_gen


async def _get_or_create_bundle_future(gen: str) -> asyncio.Future:
    """send/resend 与 SSE 共用同一 Future；若 Worker 已先完成则返回已完成的 Future。"""
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


async def _resolve_generation_future(gen: str, payload: dict[str, Any]) -> None:
    """唤醒等待中的 SSE；若无 waiter 则写入缓存供后续 get_or_create 立即取走。"""
    async with _gen_future_lock:
        fut = _generation_futures.get(gen)
        if fut is not None and not fut.done():
            fut.set_result(payload)
            return
        # 尚无 Future（例如 instant 调度在 StreamingResponse 被读前已跑完）
        _generation_results[gen] = payload


# ============ 落库与后置任务 ============


async def _post_bundle_success_tasks(
    user_id: int,
    bundled_user_text: str,
    ai_reply: str,
    emotion_data: dict,
    persona_risk_flag: bool,
    persona_risk_type: str | None,
    memory_injected: list | None,
) -> None:
    """成长、记忆提取、Redis ai_emotion（与旧 _post_chat_tasks 后置部分一致）。"""
    try:
        try:
            conversation_content = "\n".join(
                [f"用户：{ln}" for ln in bundled_user_text.split("\n") if ln.strip()]
            )
            conversation_content = f"{conversation_content}\n林小梦：{ai_reply}"
            await memory_service.extract_and_save(user_id, conversation_content)
        except Exception:
            logger.exception("记忆提取失败: user_id=%d", user_id)

        try:
            async with async_session_maker() as db:
                svc = RelationshipService(db)
                result = await svc.add_growth(user_id, "dialog")
                await db.commit()
                if result.get("leveled_up"):
                    logger.info("用户 %d 升级至 %s", user_id, result.get("new_level_name"))
        except Exception:
            logger.exception("更新成长值失败: user_id=%d", user_id)

        r = None
        try:
            r = await get_redis()
            await r.set(
                f"ai_emotion:{user_id}",
                json.dumps(emotion_data, ensure_ascii=False),
                ex=86400,
            )
        except Exception:
            logger.exception("更新 AI 情绪到 Redis 失败: user_id=%d", user_id)
        try:
            if r is None:
                r = await get_redis()
            # TD-020 V3-A：user_emotion:{user_id} + DB，与 ai_emotion 分层；失败不阻断成长/记忆
            await user_short_term_emotion_service.persist_after_round(user_id, emotion_data, r)
        except Exception:
            logger.exception("更新用户短期情绪失败: user_id=%d", user_id)
    except Exception:
        logger.exception("后置任务异常: user_id=%d", user_id)


async def _persist_bundle_success(
    user_id: int,
    pack_rows: list[ConversationLog],
    emotion_data: dict,
    ai_reply: str,
    memory_injected: list | None,
) -> None:
    """同一事务：pack 内 user 标已送达、写 assistant、写 emotion_log（挂首条 user id）。"""
    async with async_session_maker() as db:
        try:
            # TD-016 / V2-B：按轮写入；round_id 在本轮成功闭环时生成，逻辑上与 pack 内首条 user（pack_rows[0]）同属一轮
            round_id = str(uuid.uuid4())

            seqs = await allocate_sort_seq(user_id, count=1, db=db)
            asst_seq = seqs[0]

            for row in pack_rows:
                u = await db.get(ConversationLog, row.id)
                if u is not None:
                    u.delivery_status = DELIVERY_STATUS_DELIVERED
                    u.skipped_in_prompt = False
                    u.round_id = round_id

            ai_log = ConversationLog(
                user_id=user_id,
                role="assistant",
                content=ai_reply,
                sort_seq=asst_seq,
                delivery_status=None,
                skipped_in_prompt=False,
                round_id=round_id,
            )
            db.add(ai_log)
            await db.flush()

            anchor_user_id = pack_rows[0].id
            elog = EmotionLog(
                user_id=user_id,
                emotion_label=emotion_data.get("label", "平静"),
                confidence=float(emotion_data.get("confidence", 1.0)),
                conversation_id=anchor_user_id,
                round_id=round_id,
            )
            db.add(elog)
            await db.commit()
            logger.info(
                "对话闭环已落库 user_id=%d pack=%s assistant_seq=%s",
                user_id,
                [r.id for r in pack_rows],
                asst_seq,
            )
        except Exception:
            await db.rollback()
            logger.exception("闭环落库失败 user_id=%d", user_id)
            raise


async def _mark_pack_failed(
    pack_rows: list[ConversationLog],
    status: str = DELIVERY_STATUS_FAILED_TIMEOUT,
) -> None:
    ids = [r.id for r in pack_rows]
    async with async_session_maker() as db:
        try:
            for pid in ids:
                u = await db.get(ConversationLog, pid)
                if u is not None:
                    u.delivery_status = status
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("标记失败态落库异常")


async def _mark_outside_pack_skipped(session: AsyncSession, open_rows: list[ConversationLog], pack_rows: list[ConversationLog]) -> None:
    """Q14：未进入本轮 Prompt 的更早 user 行打标（仍在未闭环窗口内）。"""
    pack_ids = {r.id for r in pack_rows}
    for row in open_rows:
        if row.id not in pack_ids:
            u = await session.get(ConversationLog, row.id)
            if u is not None:
                u.skipped_in_prompt = True


async def _execute_llm_bundle(user_id: int) -> None:
    """防抖结束后执行：打包未闭环窗口 → LLM → 校验 generation → 落库或叹号。"""
    try:
        async with async_session_maker() as db:
            gen_before = await redis_get_generation(user_id)
            if not gen_before:
                return

            open_rows = await _fetch_open_window_user_rows(db, user_id)
            if not open_rows:
                return

            # 取本轮参与 Prompt 的最后 10 条 user（时间序）
            if len(open_rows) > 10:
                pack_rows = open_rows[-10:]
                await _mark_outside_pack_skipped(db, open_rows, pack_rows)
                await db.commit()
                pack_ids = [r.id for r in pack_rows]
                pack_rows = []
                for pid in pack_ids:
                    row = await db.get(ConversationLog, pid)
                    if row is not None:
                        pack_rows.append(row)
            else:
                pack_rows = list(open_rows)

            if not pack_rows:
                return

            last_user_text = pack_rows[-1].content
            user_embedding = await _get_embedding(last_user_text)
            memories_raw: list[dict] = []
            if user_embedding:
                try:
                    memories_raw = await _search_memories(user_embedding, user_id)
                except Exception as e:
                    logger.error("向量检索失败: user_id=%d err=%s", user_id, e)

            class _MemoryProxy:
                def __init__(self, content: str):
                    self.content = content

            memories = [_MemoryProxy(m["content"]) for m in memories_raw if m.get("content")]

            recent_conversations = await _get_recent_conversations(user_id, db=db, limit=20)
            recent_10 = recent_conversations[-10:] if len(recent_conversations) > 10 else recent_conversations
            relationship_info = await _get_relationship(user_id, db=db)
            redis_for_emotion = await get_redis()
            emotion_context = await user_short_term_emotion_service.read_for_prompt(
                user_id, db, redis_for_emotion
            )

            bundled = "\n".join(r.content for r in pack_rows)
            builder = PromptBuilder(db)
            prompt = await builder.build_chat_prompt(
                user_id=user_id,
                user_input=bundled,
                memories=memories,
                recent_conversations=recent_10,
                relationship_info=relationship_info,
                emotion_context=emotion_context,
            )

            gen_check = await redis_get_generation(user_id)
            if gen_check != gen_before:
                return

            try:
                result = await llm_service.chat_with_parse_strict(
                    prompt,
                    timeout_sec=get_llm_timeout_chat_seconds(),
                )
            except Exception as e:
                logger.error("LLM 失败 user_id=%d: %s", user_id, e)
                gen_after = await redis_get_generation(user_id)
                if gen_after == gen_before:
                    await _mark_pack_failed(pack_rows, DELIVERY_STATUS_FAILED_TIMEOUT)
                    await _resolve_generation_future(
                        gen_before,
                        {"error": True, "code": ERR_LLM_FAILED, "message": str(e)},
                    )
                return

            gen_after_llm = await redis_get_generation(user_id)
            if gen_after_llm != gen_before:
                return

            memory_injected = [
                {"content": m["content"], "score": m["score"]}
                for m in memories_raw
                if m.get("content")
            ] or None

            await _persist_bundle_success(
                user_id=user_id,
                pack_rows=pack_rows,
                emotion_data=result["emotion"],
                ai_reply=result["reply"],
                memory_injected=memory_injected,
            )

            first = pack_rows[0]
            asyncio.create_task(
                _post_bundle_success_tasks(
                    user_id=user_id,
                    bundled_user_text=bundled,
                    ai_reply=result["reply"],
                    emotion_data=result["emotion"],
                    persona_risk_flag=first.persona_risk_flag,
                    persona_risk_type=first.persona_risk_type,
                    memory_injected=memory_injected,
                )
            )

            await _resolve_generation_future(
                gen_before,
                {
                    "error": False,
                    "reply": result["reply"],
                    "emotion": result["emotion"],
                },
            )
    except Exception as e:
        logger.exception("打包调度异常 user_id=%d: %s", user_id, e)
        try:
            gen_b = await redis_get_generation(user_id)
            if gen_b:
                await _resolve_generation_future(
                    gen_b,
                    {"error": True, "code": ERR_LLM_FAILED, "message": str(e)},
                )
        except Exception:
            pass


# ============ SSE ============


async def _sse_chat_wait_bundle(
    user_id: int,
    generation_id: str,
):
    """首帧 meta generation_id；等待闭环结果后流式输出或 failed/obsolete。"""
    meta = json.dumps({"type": "meta", "generation_id": generation_id}, ensure_ascii=False)
    yield f"data: {meta}\n\n"

    fut = await _get_or_create_bundle_future(generation_id)
    try:
        payload = await asyncio.wait_for(fut, timeout=_BUNDLE_WAIT_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        err = json.dumps(
            {"type": "failed", "code": ERR_LLM_FAILED, "message": "等待回复超时"},
            ensure_ascii=False,
        )
        yield f"data: {err}\n\n"
        return
    finally:
        async with _gen_future_lock:
            _generation_futures.pop(generation_id, None)
            _generation_results.pop(generation_id, None)

    if payload.get("obsolete"):
        obs = json.dumps({"type": "obsolete"}, ensure_ascii=False)
        yield f"data: {obs}\n\n"
        return

    if payload.get("error"):
        err = json.dumps(
            {
                "type": "failed",
                "code": payload.get("code", ERR_LLM_FAILED),
                "message": payload.get("message", "LLM 失败"),
            },
            ensure_ascii=False,
        )
        yield f"data: {err}\n\n"
        return

    reply = payload.get("reply") or ""
    emotion_data = payload.get("emotion") or {"label": "平静", "confidence": 1.0}

    for i in range(0, len(reply), _SSE_CHUNK_SIZE):
        chunk = reply[i : i + _SSE_CHUNK_SIZE]
        event = json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False)
        yield f"data: {event}\n\n"
        await asyncio.sleep(_SSE_CHUNK_DELAY)

    done_event = json.dumps({"type": "done", "emotion": emotion_data}, ensure_ascii=False)
    yield f"data: {done_event}\n\n"


# ============ API ============


@router.post("/send")
async def chat_send(
    req: ChatSendRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_content = req.content.strip()
    if not user_content:
        return ApiResponse.fail(ERR_CONTENT_EMPTY)

    try:
        recent_conversations, relationship_info, emotion_context, user_embedding = await asyncio.gather(
            _get_recent_conversations(user_id, limit=20),
            _get_relationship(user_id),
            _get_latest_emotion(user_id),
            _get_embedding(user_content),
        )
    except Exception as e:
        logger.error("步骤1并行任务失败: user_id=%d, error=%s", user_id, str(e))
        return ApiResponse.fail(ERR_LLM_FAILED)

    memories_raw: list[dict] = []
    if user_embedding:
        try:
            memories_raw = await _search_memories(user_embedding, user_id)
        except Exception as e:
            logger.error("向量检索失败: user_id=%d, error=%s", user_id, str(e))

    safety_result = await check_content(user_content)
    if not safety_result["is_safe"]:
        logger.warning("用户输入未通过安全检查: user_id=%d", user_id)
        return ApiResponse.fail(ERR_CONTENT_UNSAFE)

    persona_risk_flag, persona_risk_type = _detect_persona_risk(user_content)
    memory_injected = [
        {"content": m["content"], "score": m["score"]}
        for m in memories_raw
        if m.get("content")
    ] or None

    open_rows = await _fetch_open_window_user_rows(db, user_id)
    if _should_block_new_send(open_rows):
        return ApiResponse.fail(ERR_CHAT_QUEUE_FULL)

    generation_id = await _new_generation_for_user(user_id)
    await _get_or_create_bundle_future(generation_id)

    seqs = await allocate_sort_seq(user_id, count=1, db=db)
    user_log = ConversationLog(
        user_id=user_id,
        role="user",
        content=user_content,
        memory_injected=memory_injected,
        persona_risk_flag=persona_risk_flag,
        persona_risk_type=persona_risk_type,
        sort_seq=seqs[0],
        delivery_status=DELIVERY_STATUS_PENDING_LLM,
        skipped_in_prompt=False,
    )
    db.add(user_log)
    await db.commit()

    async def _debounced_run() -> None:
        await _execute_llm_bundle(user_id)

    await schedule_debounced(user_id, _debounced_run)

    return StreamingResponse(
        _sse_chat_wait_bundle(user_id, generation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/resend")
async def chat_resend(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    req: ChatResendRequest = ChatResendRequest(),
):
    """叹号重发：不插入 user；限流 2 次/分钟；立即调度打包 LLM（无防抖）。"""
    open_rows = await _fetch_open_window_user_rows(db, user_id)
    if not _open_window_has_bang(open_rows):
        return ApiResponse.fail(ERR_CHAT_NOTHING_TO_RESEND)

    batch_key = str(min(r.sort_seq for r in open_rows))
    if not await try_consume_resend_quota(user_id, batch_key):
        return ApiResponse.fail(ERR_CHAT_RESEND_LIMIT)

    generation_id = await _new_generation_for_user(user_id)
    await _get_or_create_bundle_future(generation_id)
    asyncio.create_task(_execute_llm_bundle(user_id))

    return StreamingResponse(
        _sse_chat_wait_bundle(user_id, generation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history")
async def chat_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_filter = ConversationLog.user_id == user_id

    count_stmt = select(func.count()).select_from(ConversationLog).where(base_filter)
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * page_size
    list_stmt = (
        select(ConversationLog)
        .where(base_filter)
        .order_by(desc(ConversationLog.created_at), desc(ConversationLog.id))
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(list_stmt)
    rows = result.scalars().all()

    messages = [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "emotion_label": row.emotion_label,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]

    return ApiResponse.ok(
        data={
            "messages": messages,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


def _timeline_conv_item(row: ConversationLog) -> dict[str, Any]:
    """timeline 单条 conversation_log：含 delivery_status / skipped_in_prompt / sort_seq（A1 助手 null）。"""
    if row.role == "assistant":
        ds: str | None = None
        sk: bool | None = None
    else:
        ds = row.delivery_status
        sk = bool(row.skipped_in_prompt) if row.skipped_in_prompt is not None else False

    return {
        "source": row.role,
        "sort_seq": row.sort_seq,
        "id": row.id,
        "content": row.content,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "emotion_label": row.emotion_label,
        "is_read": None,
        "trigger_type": None,
        "delivery_status": ds,
        "skipped_in_prompt": sk,
    }


@router.get("/timeline")
async def chat_timeline(
    cursor: int | None = Query(None, description="游标：上一页返回的 next_cursor（sort_seq 值），首屏不传"),
    limit: int = Query(20, ge=1, le=50, description="每页数量"),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fetch_limit = limit + 1

    conv_filter = ConversationLog.user_id == user_id
    if cursor is not None:
        conv_filter = conv_filter & (ConversationLog.sort_seq < cursor)
    conv_stmt = (
        select(ConversationLog)
        .where(conv_filter)
        .order_by(desc(ConversationLog.sort_seq))
        .limit(fetch_limit)
    )
    conv_result = await db.execute(conv_stmt)
    conv_rows = list(conv_result.scalars().all())

    agent_filter = AgentMessage.user_id == user_id
    if cursor is not None:
        agent_filter = agent_filter & (AgentMessage.sort_seq < cursor)
    agent_stmt = (
        select(AgentMessage)
        .where(agent_filter)
        .order_by(desc(AgentMessage.sort_seq))
        .limit(fetch_limit)
    )
    agent_result = await db.execute(agent_stmt)
    agent_rows = list(agent_result.scalars().all())

    merged: list[dict[str, Any]] = []
    for row in conv_rows:
        merged.append(_timeline_conv_item(row))

    for row in agent_rows:
        merged.append(
            {
                "source": "agent",
                "sort_seq": row.sort_seq,
                "id": row.id,
                "content": row.content,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "emotion_label": None,
                "is_read": row.is_read,
                "trigger_type": row.trigger_type,
                "delivery_status": None,
                "skipped_in_prompt": None,
            }
        )

    merged.sort(key=lambda x: x["sort_seq"], reverse=True)

    has_more = len(merged) > limit
    page_items = merged[:limit]
    page_items.reverse()

    next_cursor = page_items[0]["sort_seq"] if page_items and has_more else None

    return ApiResponse.ok(
        data={
            "items": page_items,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }
    )
