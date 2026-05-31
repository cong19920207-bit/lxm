# -*- coding: utf-8 -*-
# 对话相关 API：TD-015 入队即落库、generation、防抖调度、打包 LLM、叹号重发、SSE meta

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_llm_timeout_chat_seconds
from backend.constants import (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_FAILED_BLOCKED,
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
from backend.services.llm_service import Step5ParseError, llm_service, merge_messages_if_exceed
from backend.services.multi_vector_retrieval_service import execute_multi_vector_retrieval
from backend.services.prompt_builder import (
    DEFAULT_PERSONA,
    LEVEL_DEFINITIONS,
    PromptBuilder,
    REDIS_KEY_PERSONA,
    _generate_time_description,
    get_activity_description,
)
from backend.services.query_rewrite_service import execute_query_rewrite
from backend.services.step5_5_service import execute_step5_5
from backend.services.step6_orchestrator import Step6Snapshot, execute_step6
from backend.services.relationship_service import RelationshipService
from backend.services import user_short_term_emotion_service
from backend.services.timeline_seq_service import allocate_sort_seq
from backend.utils.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["对话"])

_SSE_CHUNK_SIZE = 2
_SSE_CHUNK_DELAY = 0.03

# 每代 SSE 等待 LLM 闭环结果；§2.11.2 调至 120s，Nginx proxy_read_timeout 须 ≥ 130s
_BUNDLE_WAIT_TIMEOUT_SEC = 120.0

# bundled 截断上限（C28/C29）：取尾部 4000 字符（约 1500~2000 Token，
# 在阿里云 text-embedding-v3 安全范围内）。Step1.5 输入与降级 fallback_embedding 共用。
BUNDLED_MAX_CHARS = 4000


def _truncate_bundled(text: str) -> str:
    """取尾部 BUNDLED_MAX_CHARS 字符；尾部语义更重要（最后几条消息，C29）。"""
    return text[-BUNDLED_MAX_CHARS:] if len(text) > BUNDLED_MAX_CHARS else text

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


def _detect_persona_risk(text: str) -> tuple[bool, str | None]:
    text_lower = text.lower()
    for risk_type, keywords in PERSONA_RISK_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return True, risk_type
    return False, None


# ============ 内容安全：messages 逐条检测 ============


async def _check_messages_safety(messages: list) -> tuple[bool, str]:
    """
    对 messages 数组逐条执行内容安全检测。

    Args:
        messages: MessageItem 列表（需有 .content 属性或 dict["content"]）

    Returns:
        (is_safe, reason): 全部安全返回 (True, "")，任一违规返回 (False, reason)
    """
    for idx, msg in enumerate(messages):
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        if not content or not content.strip():
            continue
        result = await check_content(content)
        if not result["is_safe"]:
            reason = f"messages[{idx}] {result['reason']}"
            logger.warning("AI输出内容安全拦截: %s", reason)
            return False, reason
    return True, ""


async def _check_inner_monologue_safety(inner_monologue: str, user_id: int) -> str:
    """
    检测 inner_monologue 内容安全，违规时仅写日志 + 返回空串，不拦截整轮。

    §9.3：inner_monologue 检测失败时替换为空串，避免污染 Step6 记忆。
    """
    if not inner_monologue or not inner_monologue.strip():
        return inner_monologue
    result = await check_content(inner_monologue)
    if not result["is_safe"]:
        logger.warning(
            "inner_monologue 内容安全违规(仅日志): user_id=%d reason=%s",
            user_id, result["reason"],
        )
        return ""
    return inner_monologue


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
    ai_reply: str,
    emotion_data: dict,
    persona_risk_flag: bool,
    persona_risk_type: str | None,
) -> None:
    """成长、Redis ai_emotion（与旧 _post_chat_tasks 后置部分一致）。

    M1/§6.1.1：第一套记忆提取（extract_and_save）已下线，本后置任务不再触发记忆提取；
    记忆统一由 Step6 异步管线写入。bundled_user_text / memory_injected 死参数同步移除。
    """
    try:
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
    messages: list,
    memory_injected: list | None,
    round_id: str,
) -> None:
    """同一事务：pack 内 user 标已送达、写 N 条 assistant（每条对应 messages[i]）、写 emotion_log。

    §2.8.1：messages 有几条就写入几条 role=assistant，round_id 共享。
    §2.8.3：一次性申请 N 个连续 sort_seq，按数组下标从小到大赋值。
    """
    msg_count = len(messages)
    if msg_count < 1:
        logger.warning("_persist_bundle_success: messages 为空，跳过落库 user_id=%d", user_id)
        return

    async with async_session_maker() as db:
        try:
            # 一次性申请 N 个连续 sort_seq
            seqs = await allocate_sort_seq(user_id, count=msg_count, db=db)

            for row in pack_rows:
                u = await db.get(ConversationLog, row.id)
                if u is not None:
                    u.delivery_status = DELIVERY_STATUS_DELIVERED
                    u.skipped_in_prompt = False
                    u.round_id = round_id

            # 按数组下标写入 N 条 assistant 行
            for idx, msg in enumerate(messages):
                content = msg.content if hasattr(msg, "content") else msg.get("content", "")
                ai_log = ConversationLog(
                    user_id=user_id,
                    role="assistant",
                    content=content,
                    sort_seq=seqs[idx],
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
                "对话闭环已落库 user_id=%d pack=%s assistant_seqs=%s msg_count=%d",
                user_id,
                [r.id for r in pack_rows],
                seqs,
                msg_count,
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


def _build_round_context(
    relationship_info: Relationship | None,
    time_description: str,
    activity_description: str,
) -> dict:
    """
    STEP-018：构建本轮内存上下文 dict，供 Prompt 构建 / Step5.5 / Step6 共用。

    扩展字段为 NULL 时使用占位文案（空串或默认描述）。
    """
    if relationship_info is not None:
        _rel_level = relationship_info.level
        _level_name = LEVEL_DEFINITIONS.get(_rel_level, LEVEL_DEFINITIONS[0])["name"]

        if relationship_info.last_interaction_at:
            _silence_days = (datetime.utcnow() - relationship_info.last_interaction_at).days
        else:
            _silence_days = 999
    else:
        _rel_level = 0
        _level_name = LEVEL_DEFINITIONS[0]["name"]
        _silence_days = 999

    def _safe(val: str | None, fallback: str = "") -> str:
        return val if val else fallback

    return {
        "time_description": time_description,
        "activity_description": activity_description,
        "relation_description": _safe(
            getattr(relationship_info, "relation_description", None) if relationship_info else None,
            "暂无，初次互动",
        ),
        "user_real_name": _safe(
            getattr(relationship_info, "user_real_name", None) if relationship_info else None,
        ),
        "user_hobby_name": _safe(
            getattr(relationship_info, "user_hobby_name", None) if relationship_info else None,
        ),
        "user_description": _safe(
            getattr(relationship_info, "user_description", None) if relationship_info else None,
        ),
        "character_purpose": _safe(
            getattr(relationship_info, "character_purpose", None) if relationship_info else None,
        ),
        "character_attitude": _safe(
            getattr(relationship_info, "character_attitude", None) if relationship_info else None,
        ),
        "level": _rel_level,
        "level_name": _level_name,
        "silence_days": _silence_days,
    }


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

            # 整包拼接 + 截断（C24/C28/C29）：bundled 供 Step5（build_chat_prompt 的
            # user_input）使用整包；bundled_truncated 供 Step1.5（rewrite_input）与
            # 降级 fallback_embedding 共用同一截断结果。C39：删除原 last_user_text 死变量。
            bundled = "\n".join(r.content for r in pack_rows)
            bundled_truncated = _truncate_bundled(bundled)

            recent_conversations = await _get_recent_conversations(user_id, db=db, limit=20)
            recent_10 = recent_conversations[-10:] if len(recent_conversations) > 10 else recent_conversations
            relationship_info = await _get_relationship(user_id, db=db)
            redis_for_emotion = await get_redis()
            emotion_context = await user_short_term_emotion_service.read_for_prompt(
                user_id, db, redis_for_emotion
            )

            # ── STEP-018：构建本轮内存上下文，供 Step1.5 / Step3 / Step6 共用 ──
            time_description = _generate_time_description()
            activity_description = await get_activity_description()

            round_context = _build_round_context(
                relationship_info=relationship_info,
                time_description=time_description,
                activity_description=activity_description,
            )

            # ── STEP-019 + STEP-020：Step1.5 查询重写 → Step2 多路向量检索 ──
            r_for_persona = await get_redis()
            _persona_text = await r_for_persona.get(REDIS_KEY_PERSONA)
            if not _persona_text:
                _persona_text = DEFAULT_PERSONA

            query_rewrite_result = await execute_query_rewrite(
                user_id=user_id,
                rewrite_input=bundled_truncated,
                persona_text=_persona_text,
                round_context=round_context,
                recent_conversations=recent_10,
                source="main",
            )

            retrieval_result = await execute_multi_vector_retrieval(
                query_rewrite_result=query_rewrite_result,
                user_id=user_id,
            )

            # Step2 检索结果：user_results 供 User Memory 模块，四路结果供模块 A
            memories_raw = retrieval_result.user_memory_results
            retrieval_for_prompt = retrieval_result.format_for_prompt()

            # bundled 已在上方（Step1.5 调用前）定义并复用，Step5 user_input 仍传整包（C39）
            builder = PromptBuilder(db)
            prompt = await builder.build_chat_prompt(
                user_id=user_id,
                user_input=bundled,
                memories=memories_raw,
                recent_conversations=recent_10,
                relationship_info=relationship_info,
                emotion_context=emotion_context,
                round_context=round_context,
                retrieval_results=retrieval_for_prompt,
            )

            gen_check = await redis_get_generation(user_id)
            if gen_check != gen_before:
                return

            try:
                step5_result = await llm_service.chat_with_step5_parse(
                    prompt,
                    timeout_sec=get_llm_timeout_chat_seconds(),
                )
            except (Step5ParseError, Exception) as e:
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

            # ── §9.1 内容安全：inner_monologue 检测（违规仅日志+替换空串，不拦截）──
            step5_result.inner_monologue = await _check_inner_monologue_safety(
                step5_result.inner_monologue, user_id
            )

            # ── §9.1 内容安全：Step5 messages 逐条检测（任一违规→整轮失败，不进5.5）──
            step5_msgs_safe, step5_msgs_reason = await _check_messages_safety(
                step5_result.messages
            )
            if not step5_msgs_safe:
                logger.warning(
                    "Step5 messages 内容安全拦截 user_id=%d: %s", user_id, step5_msgs_reason
                )
                await _mark_pack_failed(pack_rows, DELIVERY_STATUS_FAILED_BLOCKED)
                await _resolve_generation_future(
                    gen_before,
                    {"error": True, "code": ERR_CONTENT_UNSAFE, "message": "内容安全拦截"},
                )
                return

            # §2.9.3：Step5 解析成功即生成 round_id，后续落库和 Step6 入队复用同一值
            round_id = str(uuid.uuid4())

            # ── §2.9.3 CP1 消费点 3：Step6 入参快照，对 Step5 原始 messages 执行合并 ──
            # R-BND-05：Step6 仅吃 Step5 原始产出，不使用 Step5.5 输出
            step6_messages = merge_messages_if_exceed(step5_result.messages)

            # ── Step5.5 响应润色（§2.7.1 双门闩 OR 触发）──
            # STEP-018：从 round_context 取关系等级名称，与 Step3/Step6 共用同一份
            _level_name = round_context["level_name"]

            step5_5_result = await execute_step5_5(
                step5_messages=step5_result.messages,
                step5_inner_monologue=step5_result.inner_monologue,
                step5_emotion_label=step5_result.emotion.label,
                step5_emotion_confidence=step5_result.emotion.confidence,
                step5_relation_change_delta=step5_result.relation_change.delta,
                step5_future_time_natural=step5_result.future.time_natural,
                step5_future_action=step5_result.future.action,
                step5_knowledge_expand=step5_result.knowledge_expand,
                level_name=_level_name,
                user_hobby_name=round_context["user_hobby_name"] or None,
                user_real_name=round_context["user_real_name"] or None,
                recent_conversations=recent_10,
            )

            if step5_5_result is not None:
                # ── §9.1 内容安全：Step5.5 输出逐条检测（违规→回退 Step5）──
                step5_5_safe, step5_5_reason = await _check_messages_safety(
                    step5_5_result
                )
                if step5_5_safe:
                    final_messages = step5_5_result
                else:
                    logger.warning(
                        "Step5.5 输出内容安全拦截，回退Step5 user_id=%d: %s",
                        user_id, step5_5_reason,
                    )
                    final_messages = merge_messages_if_exceed(step5_result.messages)
            else:
                # Step5.5 未触发或失败回退：使用 Step5 原始 messages（经合并后的版本）
                final_messages = merge_messages_if_exceed(step5_result.messages)

            # 从 Step5 结构化输出提取兼容字段（使用合并后的 messages）
            ai_reply = "\n".join(m.content for m in final_messages)
            emotion_data = {
                "label": step5_result.emotion.label,
                "confidence": step5_result.emotion.confidence,
            }

            memory_injected = [
                {"content": m["content"], "score": m["score"]}
                for m in memories_raw
                if m.get("content")
            ] or None

            await _persist_bundle_success(
                user_id=user_id,
                pack_rows=pack_rows,
                emotion_data=emotion_data,
                messages=final_messages,
                memory_injected=memory_injected,
                round_id=round_id,
            )

            first = pack_rows[0]
            asyncio.create_task(
                _post_bundle_success_tasks(
                    user_id=user_id,
                    ai_reply=ai_reply,
                    emotion_data=emotion_data,
                    persona_risk_flag=first.persona_risk_flag,
                    persona_risk_type=first.persona_risk_type,
                )
            )

            # ── §2.9.3 / §2.8.4：Step6 异步入队（M2 半异步，不阻塞 SSE）──
            # _persona_text 已在 Step1.5 阶段获取，此处直接复用
            try:
                _recent_conv_snapshot = [
                    {"role": c.role, "content": c.content} for c in recent_10
                ]

                # STEP-018：从 round_context 取关系扩展字段，与 Step5.5 共用同一份
                step6_snapshot = Step6Snapshot(
                    user_id=user_id,
                    round_id=round_id,
                    step6_messages=step6_messages,
                    user_input=bundled,
                    persona_text=_persona_text,
                    level_name=_level_name,
                    relation_description=round_context["relation_description"] or None,
                    user_real_name=round_context["user_real_name"] or None,
                    user_hobby_name=round_context["user_hobby_name"] or None,
                    user_description=round_context["user_description"] or None,
                    character_purpose=round_context["character_purpose"] or None,
                    character_attitude=round_context["character_attitude"] or None,
                    recent_conversations=_recent_conv_snapshot,
                    future_time_natural=step5_result.future.time_natural,
                    future_action=step5_result.future.action,
                )
                asyncio.create_task(execute_step6(step6_snapshot))
            except Exception:
                logger.exception("Step6 入队失败(不影响主链): user_id=%d", user_id)

            # 将合并后的结构化数据写入 Future payload，供 SSE / done / 后续环节使用
            step5_dump = step5_result.model_dump()
            step5_dump["messages"] = [m.model_dump() for m in final_messages]
            await _resolve_generation_future(
                gen_before,
                {
                    "error": False,
                    "reply": ai_reply,
                    "emotion": emotion_data,
                    "step5": step5_dump,
                    "round_id": round_id,
                    "step6_messages": [m.model_dump() for m in step6_messages],
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
    """§2.9.4 多气泡 SSE：meta(message_count) → delta(message_index) → done(messages+emotion)。"""

    fut = await _get_or_create_bundle_future(generation_id)
    try:
        payload = await asyncio.wait_for(fut, timeout=_BUNDLE_WAIT_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        # 超时也先发 meta，保证前端能识别流
        meta = json.dumps({"type": "meta", "generation_id": generation_id, "message_count": 0}, ensure_ascii=False)
        yield f"data: {meta}\n\n"
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
        meta = json.dumps({"type": "meta", "generation_id": generation_id, "message_count": 0}, ensure_ascii=False)
        yield f"data: {meta}\n\n"
        obs = json.dumps({"type": "obsolete"}, ensure_ascii=False)
        yield f"data: {obs}\n\n"
        return

    if payload.get("error"):
        meta = json.dumps({"type": "meta", "generation_id": generation_id, "message_count": 0}, ensure_ascii=False)
        yield f"data: {meta}\n\n"
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

    # 提取多条 messages（Step5 结构化输出）
    step5_data = payload.get("step5") or {}
    messages_raw = step5_data.get("messages") or []
    emotion_data = payload.get("emotion") or {"label": "平静", "confidence": 1.0}

    # 兜底：若 step5.messages 为空则回退到 reply 单条
    if not messages_raw:
        reply = payload.get("reply") or ""
        messages_raw = [{"type": "text", "content": reply}] if reply else []

    message_count = len(messages_raw)

    # CP2：首包携带 message_count + generation_id
    meta = json.dumps(
        {"type": "meta", "generation_id": generation_id, "message_count": message_count},
        ensure_ascii=False,
    )
    yield f"data: {meta}\n\n"

    # 按条推送 delta：每条 message 按 chunk 拆分，携带 message_index
    for msg_idx, msg in enumerate(messages_raw):
        content = msg.get("content") or ""
        for i in range(0, len(content), _SSE_CHUNK_SIZE):
            chunk = content[i : i + _SSE_CHUNK_SIZE]
            event = json.dumps(
                {"type": "delta", "content": chunk, "message_index": msg_idx},
                ensure_ascii=False,
            )
            yield f"data: {event}\n\n"
            await asyncio.sleep(_SSE_CHUNK_DELAY)

    # done 携带完整 messages 数组 + emotion（真相源）
    done_messages = [{"type": m.get("type", "text"), "content": m.get("content", "")} for m in messages_raw]
    done_event = json.dumps(
        {"type": "done", "messages": done_messages, "emotion": emotion_data},
        ensure_ascii=False,
    )
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

    # M11/P7：send 阶段不再做向量检索/记忆注入计算（无下游消费者，已删 gather 三件套
    # + _search_memories + memory_injected 计算）；记忆召回统一在 _execute_llm_bundle 内
    # Step1.5→Step2 路径完成。conversation_log.memory_injected 列保留，新 user 行恒 null。
    safety_result = await check_content(user_content)
    if not safety_result["is_safe"]:
        logger.warning("用户输入未通过安全检查: user_id=%d", user_id)
        return ApiResponse.fail(ERR_CONTENT_UNSAFE)

    persona_risk_flag, persona_risk_type = _detect_persona_risk(user_content)

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
        memory_injected=None,  # M11：新 user 行恒 null
        persona_risk_flag=persona_risk_flag,
        persona_risk_type=persona_risk_type,
        sort_seq=seqs[0],
        delivery_status=DELIVERY_STATUS_PENDING_LLM,
        skipped_in_prompt=False,
    )
    db.add(user_log)
    await db.commit()

    # R-FUT-03：用户发新消息时将 proactive_times 清零
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
