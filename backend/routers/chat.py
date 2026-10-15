# -*- coding: utf-8 -*-
# 对话相关 API：TD-015 入队即落库、generation、防抖调度、打包 LLM、叹号重发、SSE meta

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_llm_timeout_chat_seconds
from backend.constants import (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_FAILED_BLOCKED,
    DELIVERY_STATUS_FAILED_ERROR,
    DELIVERY_STATUS_FAILED_TIMEOUT,
    ERR_CHAT_QUEUE_FULL,
    ERR_CONTENT_EMPTY,
    ERR_CONTENT_UNSAFE,
    ERR_LLM_FAILED,
)
from backend.services import chat_service
from backend.services.chat_client_timing import CLIENT_TIMING
from backend.services.timeline_read_service import get_timeline
from backend.database import async_session_maker, get_db
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.models.relationship import Relationship
from backend.redis_client import get_redis
from backend.schemas.chat import ChatResendRequest, ChatSendRequest
from backend.schemas.common import ApiResponse
from backend.services.chat_queue_service import (
    cancel_local_debounce_task,
    redis_get_generation,
)
from backend.services.content_safety_service import check_content  # noqa: F401 — 测试与 Step 安全链仍引用
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
from backend.services.timeline_seq_service import allocate_sort_seq
from backend.services.relationship_service import RelationshipService
from backend.services import user_short_term_emotion_service
from backend.utils.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["对话"])

_SSE_CHUNK_SIZE = 2
_SSE_CHUNK_DELAY = 0.03

# bundled 截断上限（C28/C29）：取尾部 4000 字符（约 1500~2000 Token，
# 在阿里云 text-embedding-v3 安全范围内）。Step1.5 输入与降级 fallback_embedding 共用。
BUNDLED_MAX_CHARS = 4000


def _truncate_bundled(text: str) -> str:
    """取尾部 BUNDLED_MAX_CHARS 字符；尾部语义更重要（最后几条消息，C29）。"""
    return text[-BUNDLED_MAX_CHARS:] if len(text) > BUNDLED_MAX_CHARS else text

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


_detect_persona_risk = chat_service._detect_persona_risk


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


async def _execute_llm_bundle(user_id: int, generation_id: str) -> None:
    from contextlib import suppress
    from backend.services import chat_lifecycle as life
    from backend.services.chat_lifecycle_runtime import heartbeat
    from backend.services.memory_business_guard import enter_business_epoch, business_epoch
    token = business_epoch.set(await enter_business_epoch(async_session_maker))
    try:
        handle = await life.claim(user_id,generation_id)
        if handle is None:return
        worker=asyncio.current_task()
        pulse=asyncio.create_task(heartbeat(handle,worker))
        try:
            async with asyncio.timeout(max(0,(handle.deadline_at-datetime.utcnow()).total_seconds())):
                await _run_owned_bundle(handle)
        except (TimeoutError, asyncio.CancelledError):
            await life.fail(handle,'deadline_exceeded' if datetime.utcnow()>=handle.deadline_at else 'execution_lost')
            await life.reconcile(user_id,generation_id)
        except Exception as exc:
            reason=str(exc) if str(exc) in ('prompt_budget_exceeded','prompt_budget_unverified') else 'llm_failed'
            await life.fail(handle,reason)
            await life.reconcile(user_id,generation_id)
            logger.warning('chat generation failed user=%s generation=%s reason=%s',user_id,generation_id,reason)
        finally:
            pulse.cancel()
            with suppress(asyncio.CancelledError):await pulse
    finally:business_epoch.reset(token)


async def _load_memory_context(user_id, db):
    """Read-only business adapter shared by diagnostics; no send/Step1 side effects."""
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

    return dict(persona_text=_persona_text,round_context=round_context,recent_conversations=recent_10,
        relationship_info=relationship_info,emotion_context=emotion_context)


async def _run_owned_bundle(handle) -> None:
    from backend.services import chat_lifecycle as life
    from backend.models.chat_lifecycle import ChatGenerationMessage
    from backend.services.chat_memory_pipeline import build_main_prompt,call_main_model
    user_id=handle.user_id
    async with async_session_maker() as db:
            pack_rows=list((await db.execute(select(ConversationLog).join(ChatGenerationMessage,
                ChatGenerationMessage.conversation_id==ConversationLog.id).where(
                ChatGenerationMessage.user_id==user_id,ChatGenerationMessage.generation_id==handle.generation_id,
                ChatGenerationMessage.in_prompt.is_(True),ConversationLog.user_id==user_id)
                .order_by(ChatGenerationMessage.ordinal))).scalars())
            if not pack_rows:return
            # 整包拼接 + 截断（C24/C28/C29）：bundled 供 Step5（build_chat_prompt 的
            # user_input）使用整包；bundled_truncated 供 Step1.5（rewrite_input）与
            # 降级 fallback_embedding 共用同一截断结果。C39：删除原 last_user_text 死变量。
            bundled = "\n".join(r.content for r in pack_rows)
            bundled_truncated = _truncate_bundled(bundled)

            context = await _load_memory_context(user_id, db)
            recent_10 = context['recent_conversations']
            relationship_info = context['relationship_info']
            emotion_context = context['emotion_context']
            round_context = context['round_context']
            _persona_text = context['persona_text']

            # Finish the context read transaction before inner guard/claim
            # transactions; retaining runtime fence locks would self-deadlock.
            await db.commit()
            if not await life.renew(handle,remote=True):raise life.LostOwnership()
            prepared = await build_main_prompt(handle,bundled=bundled,rewrite_input=bundled_truncated,
                persona_text=_persona_text,round_context=round_context,recent_conversations=recent_10,
                relationship_info=relationship_info,emotion_context=emotion_context)
            step5_result=await call_main_model(prepared,handle.owner)
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
                await life.fail(handle,'content_blocked')
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

            def register_success_effects():
                first = pack_rows[0]
                asyncio.create_task(
                    _run_chat_effect(handle, "post_success", _post_bundle_success_tasks(
                        user_id=user_id,
                        ai_reply=ai_reply,
                        emotion_data=emotion_data,
                        persona_risk_flag=first.persona_risk_flag,
                        persona_risk_type=first.persona_risk_type,
                    ))
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
                    asyncio.create_task(_run_chat_effect(handle, "step6", execute_step6(step6_snapshot)))
                except Exception:
                    logger.exception("Step6 入队失败(不影响主链): user_id=%d", user_id)

            await life.commit_success(handle,str(uuid.uuid4()),messages=final_messages,
                emotion=emotion_data,round_id=round_id,on_success=register_success_effects)

async def _run_chat_effect(handle,kind,coro):
    from backend.services import chat_lifecycle as life
    if not await life.claim_effect(handle,kind):
        coro.close();return
    ok=False
    try:
        await coro;ok=True
    finally:await life.finish_effect(handle,kind,ok)


# ============ SSE ============


async def _sse_chat_wait_bundle(
    user_id: int,
    generation_id: str,
    admission=None,
):
    """§2.9.4 多气泡 SSE：meta(message_count) → delta(message_index) → done(messages+emotion)。"""

    from backend.services import chat_lifecycle as life
    async def status_fields():
        if admission is None:return {}
        async with async_session_maker() as db:
            status=await life.read_status(db,user_id,admission.operation,admission.request_id)
        return {key:status[key] for key in ('operation','request_id','source_messages','accepted_generation_id',
            'effective_generation_id','effective_deadline_at','reconcile_until','state_revision','can_resend')}
    identity=await status_fields()
    payload = await chat_service.await_bundle_payload(generation_id,user_id)
    identity=await status_fields()
    if payload.get("error") and payload.get("code") == ERR_LLM_FAILED and payload.get("message") == "等待回复超时":
        meta = json.dumps({"type": "meta", "generation_id": generation_id, "message_count": 0, **identity}, ensure_ascii=False)
        yield f"data: {meta}\n\n"
        err = json.dumps(
            {"type": "failed", "code": ERR_LLM_FAILED, "message": "等待回复超时"},
            ensure_ascii=False,
        )
        yield f"data: {err}\n\n"
        return

    if payload.get("obsolete"):
        meta = json.dumps({"type": "meta", "generation_id": generation_id, "message_count": 0, **identity}, ensure_ascii=False)
        yield f"data: {meta}\n\n"
        obs = json.dumps({"type": "obsolete"}, ensure_ascii=False)
        yield f"data: {obs}\n\n"
        return

    if payload.get("error"):
        meta = json.dumps({"type": "meta", "generation_id": generation_id, "message_count": 0, **identity}, ensure_ascii=False)
        yield f"data: {meta}\n\n"
        err = json.dumps(
            {
                "type": "failed",
                "code": payload.get("code", ERR_LLM_FAILED),
                "message": payload.get("message", "LLM 失败"),
                **identity,
            },
            ensure_ascii=False,
        )
        yield f"data: {err}\n\n"
        return

    done_messages, emotion_data, _round_id = chat_service.build_done_messages_from_payload(payload)
    messages_raw = done_messages
    message_count = len(messages_raw)

    # CP2：首包携带 message_count + generation_id
    meta = json.dumps(
        {"type": "meta", "generation_id": generation_id, "message_count": message_count, **identity},
        ensure_ascii=False,
    )
    yield f"data: {meta}\n\n"

    # 按条推送 delta：每条 message 按 chunk 拆分，携带 message_index
    for msg_idx, msg in enumerate(messages_raw):
        content = msg.get("content") or ""
        for i in range(0, len(content), _SSE_CHUNK_SIZE):
            chunk = content[i : i + _SSE_CHUNK_SIZE]
            event = json.dumps(
                {"type": "delta", "content": chunk, "message_index": msg_idx,"generation_id":generation_id,"state_revision":payload.get("state_revision")},
                ensure_ascii=False,
            )
            yield f"data: {event}\n\n"
            await asyncio.sleep(_SSE_CHUNK_DELAY)

    done_event = json.dumps(
        {"type": "done", "messages": payload.get("result",{}).get("messages",done_messages), "emotion": emotion_data,"round_id":_round_id, **identity},
        ensure_ascii=False,
    )
    yield f"data: {done_event}\n\n"


# ============ API ============


@router.get("/resend-eligibility")
async def chat_resend_eligibility(user_id: int = Depends(get_current_user),db: AsyncSession = Depends(get_db)):
    from backend.services.chat_lifecycle import read_resend_eligibility
    return ApiResponse.ok(data=await read_resend_eligibility(db,user_id))


@router.get("/client-timing")
async def chat_client_timing(user_id: int = Depends(get_current_user)):
    """Authenticated configuration projection; no SQL/Redis/model writes."""
    return ApiResponse.ok(data=dict(CLIENT_TIMING))


@router.post("/send")
async def chat_send(
    req: ChatSendRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from backend.services import chat_lifecycle as life
    try:
        admission=await chat_service.submit(user_id,db,'send',req.client_message_id,_execute_llm_bundle,content=req.content)
    except life.AdmissionError as exc:return ApiResponse.fail(exc.code,data=exc.status)
    generation_id=admission.generation_id

    return StreamingResponse(
        _sse_chat_wait_bundle(user_id, generation_id,admission),
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
    from backend.services import chat_lifecycle as life
    try:admission=await chat_service.submit(user_id,db,'resend',req.client_resend_id,_execute_llm_bundle)
    except life.AdmissionError as exc:return ApiResponse.fail(exc.code,data=exc.status)
    generation_id=admission.generation_id

    return StreamingResponse(
        _sse_chat_wait_bundle(user_id, generation_id,admission),
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


@router.get("/timeline")
async def chat_timeline(
    response: Response,
    request: Request,
    pending_reload: bool = Query(False, description="既有pending卡片的一次自动重拉标记"),
    cursor: int | None = Query(None, description="游标：上一页返回的 next_cursor（sort_seq 值），首屏不传"),
    limit: int = Query(20, ge=1, le=50, description="每页数量"),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 首屏拉取时若满队且全 pending_llm，后台补跑 bundle（刷新页可自愈死锁）
    if cursor is None:
        await chat_service.trigger_recovery_if_queue_stuck(
            user_id, db, _execute_llm_bundle
        )
    response.headers['Cache-Control'] = 'no-store'
    data = await get_timeline(user_id, db, cursor=cursor, limit=limit, include_calls=True,
        metrics=getattr(request.app.state, "voice_metrics", None), pending_reload=pending_reload)
    return ApiResponse.ok(data=data)


@router.get("/submissions/{operation}/{request_id}")
async def chat_submission_status(operation:str,request_id:str,user_id:int=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    from fastapi import HTTPException
    from backend.services.chat_lifecycle import decode_request_id,read_status
    try:raw=decode_request_id(operation,request_id)
    except ValueError:raise HTTPException(422,"invalid_submission_identity") from None
    return ApiResponse.ok(data=await read_status(db,user_id,operation,raw))
