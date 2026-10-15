# -*- coding: utf-8 -*-
# Step8 子链路：Future 槽到期触发的主动消息生成，复用主链 Step 变体

import asyncio
import logging
import random
import uuid
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import PERSONA_RISK_KEYWORDS
from backend.database import async_session_maker
from backend.models.agent_message import TriggerType
from backend.models.conversation_log import ConversationLog
from backend.models.relationship import Relationship
from backend.redis_client import get_redis
from backend.services.content_safety_service import check_content
from backend.services.llm_service import merge_messages_if_exceed
from backend.services.prompt_builder import (
    DEFAULT_PERSONA,
    LEVEL_DEFINITIONS,
    REDIS_KEY_PERSONA,
    _generate_time_description,
    get_activity_description,
)
from backend.services.step5_5_service import execute_step5_5
from backend.services.step6_orchestrator import Step6Snapshot, execute_step6
from backend.services import user_short_term_emotion_service
from backend.services.agent_service import agent_service
from backend.utils.future_time_parser import parse_future_time

logger = logging.getLogger(__name__)

# Step8 子链路 Step5.5 门闩 A 概率（可配置较低值）
STEP8_GATE_A_PROBABILITY = 0.03

# 衰减门控底数
DECAY_BASE = 0.15

# 主动消息兜底回复
STEP8_FALLBACK_REPLY = "突然想起一件事想跟你说~"


from contextlib import suppress
from backend.services import future_lifecycle as life
from backend.services.step8_memory_pipeline import build_step8_prompt, call_step8_model
from backend.services.memory_business_guard import enter_business_epoch, business_epoch
from backend.services.chat_timing import TIMING

_effect_tasks = set()
_effects_by_consume = {}

def _spawn_effect(coro, consume_id=None):
    task = asyncio.create_task(coro)
    _effect_tasks.add(task)
    def done(completed):
        _effect_tasks.discard(completed)
        if consume_id is not None:
            pending = _effects_by_consume.get(consume_id, set())
            pending.discard(completed)
            if not pending:
                _effects_by_consume.pop(consume_id, None)
                life.ACTIVE_SNAPSHOTS.discard(consume_id)
        if not completed.cancelled() and completed.exception():
            logger.error('future_effect_task_failed consume=%s', consume_id, exc_info=completed.exception())
    if consume_id is not None:
        life.ACTIVE_SNAPSHOTS.add(consume_id)
        _effects_by_consume.setdefault(consume_id, set()).add(task)
    task.add_done_callback(done)
    return task

async def drain_effects():
    while _effect_tasks:
        await asyncio.gather(*tuple(_effect_tasks), return_exceptions=True)

async def _heartbeat(handle, worker):
    while True:
        await asyncio.sleep(TIMING.renew_ms / 1000)
        try:
            if not await life.renew(handle):
                worker.cancel()
                return
        except Exception:
            worker.cancel()
            return

class _SuccessEffects:
    """Keep the live worker snapshot through outer verification; notify at most once."""
    def __init__(self):
        self.marker = None
        self.callback = None
        self.notified = False

    def arm(self, callback):
        self.marker = str(uuid.uuid4())
        self.callback = callback
        return self.marker

    def confirmed(self):
        if self.callback is not None and not self.notified:
            self.notified = True
            self.callback()


async def execute_step8_subchain(user_id: int, future_action: str | None, *, slot=None):
    token = business_epoch.set(await enter_business_epoch(async_session_maker))
    handle = None
    effects = _SuccessEffects()
    try:
        slot = slot or await life.capture(user_id)
        if slot is None or slot.action != future_action:
            return life.Result(None, 'superseded')
        accepted = await life.accept(slot)
        if isinstance(accepted, life.Result):
            if accepted.consume_id:
                return await life.reconcile(user_id, accepted.consume_id)
            return accepted
        handle = accepted
        if not future_action or not future_action.strip():
            return await life.fail(handle, 'llm_failed')
        pulse = asyncio.create_task(_heartbeat(handle, asyncio.current_task()))
        try:
            async with asyncio.timeout(max(0, (handle.deadline_at-datetime.utcnow()).total_seconds())):
                result = await _execute_owned(handle, future_action, effects)
            if result.terminal == 'unverified' and effects.marker is not None:
                return await life.reconcile(user_id, handle.consume_id, marker=effects.marker,
                    handle=handle, on_success=effects.confirmed)
            return result
        except (TimeoutError, asyncio.CancelledError):
            return await _finish_owned(handle, effects, 'deadline_exceeded' if datetime.utcnow()>=handle.deadline_at else 'execution_lost')
        except Exception as exc:
            reason = str(exc) if str(exc) in ('prompt_budget_exceeded','prompt_budget_unverified') else 'llm_failed'
            return await _finish_owned(handle, effects, reason)
        finally:
            pulse.cancel()
            with suppress(asyncio.CancelledError): await pulse
    finally:
        business_epoch.reset(token)

async def _finish_owned(handle, effects, reason):
    result = await life.reconcile(handle.user_id, handle.consume_id, marker=effects.marker,
        handle=handle, on_success=effects.confirmed)
    if result.terminal == 'pending':
        return await life.fail(handle, reason)
    return result


async def _load_memory_context(user_id, db):
    """Read-only Step8 input adapter; never reads or consumes a Future slot."""
    recent_conversations = await _get_recent_conversations(user_id, db)
    relationship_info = await _get_relationship(user_id, db)
    emotion_context = await _get_emotion_context(user_id, db)
    recent_10 = recent_conversations[-10:] if len(recent_conversations) > 10 else recent_conversations
    time_description = _generate_time_description()
    activity_description = await get_activity_description()
    round_context = _build_step8_round_context(relationship_info, time_description, activity_description)
    r_for_persona = await get_redis()
    persona_text = await r_for_persona.get(REDIS_KEY_PERSONA)
    if not persona_text:
        persona_text = DEFAULT_PERSONA
    return dict(persona_text=persona_text,round_context=round_context,recent_conversations=recent_10,
        relationship_info=relationship_info,emotion_context=emotion_context)


async def _execute_owned(handle, future_action, effects):
    user_id = handle.user_id
    try:
        # ── Step1：并行装载上下文 ──
        logger.info("[Step8] 开始子链路: user_id=%d, action=%s", user_id, future_action)

        async with async_session_maker() as db:
            context = await _load_memory_context(user_id, db)
        recent_10 = context['recent_conversations']
        relationship_info = context['relationship_info']
        emotion_context = context['emotion_context']
        round_context = context['round_context']
        persona_text = context['persona_text']

        if not await life.renew(handle, remote=True):
            raise life.LostOwnership()
        prepared = await build_step8_prompt(handle, bundled=future_action, rewrite_input=future_action,
            persona_text=persona_text, round_context=round_context, recent_conversations=recent_10,
            relationship_info=relationship_info, emotion_context=emotion_context)
        step5_result = await call_step8_model(prepared, handle.owner)

        # 内容安全检测：messages 逐条
        for idx, msg in enumerate(step5_result.messages):
            content = msg.content if hasattr(msg, "content") else ""
            if content and content.strip():
                safety = await check_content(content)
                if not safety["is_safe"]:
                    logger.warning(
                        "[Step8] Step5 messages[%d] 内容安全拦截: user_id=%d", idx, user_id
                    )
                    return await life.fail(handle, "content_blocked")

        # 人格风险关键词扫描
        for msg in step5_result.messages:
            if _check_persona_risk(msg.content):
                logger.warning(
                    "[Step8] 人格风险检测命中，使用兜底: user_id=%d", user_id
                )
                return await _fallback_write_agent_message(handle, effects)

        round_id = str(uuid.uuid4())

        # CP1：Step6 入参快照使用 Step5 原始 messages 合并后版本
        step6_messages = merge_messages_if_exceed(step5_result.messages)

        # ── Step5.5：可配置较低触发概率 ──
        level_name = round_context["level_name"]

        step5_5_result = await execute_step5_5(
            step5_messages=step5_result.messages,
            step5_inner_monologue=step5_result.inner_monologue,
            step5_emotion_label=step5_result.emotion.label,
            step5_emotion_confidence=step5_result.emotion.confidence,
            step5_relation_change_delta=step5_result.relation_change.delta,
            step5_future_time_natural=step5_result.future.time_natural,
            step5_future_action=step5_result.future.action,
            step5_knowledge_expand=step5_result.knowledge_expand,
            level_name=level_name,
            user_hobby_name=round_context["user_hobby_name"] or None,
            user_real_name=round_context["user_real_name"] or None,
            recent_conversations=recent_10,
            gate_a_override=STEP8_GATE_A_PROBABILITY,
        )

        if step5_5_result is not None:
            # Step5.5 输出内容安全检测
            all_safe = True
            for msg in step5_5_result:
                content = msg.content if hasattr(msg, "content") else ""
                if content and content.strip():
                    safety = await check_content(content)
                    if not safety["is_safe"]:
                        all_safe = False
                        break
            final_messages = step5_5_result if all_safe else merge_messages_if_exceed(step5_result.messages)
        else:
            final_messages = merge_messages_if_exceed(step5_result.messages)

        # ── 写入 agent_message 表（不走 SSE）──
        reply_text = "\n".join(m.content for m in final_messages)

        recent_conv_snapshot = [{"role": c.role, "content": c.content} for c in recent_10]
        step6_snapshot = Step6Snapshot(
            user_id=user_id, round_id=round_id, step6_messages=step6_messages,
            user_input=future_action, persona_text=persona_text, level_name=level_name,
            relation_description=round_context["relation_description"] or None,
            user_real_name=round_context["user_real_name"] or None,
            user_hobby_name=round_context["user_hobby_name"] or None,
            user_description=round_context["user_description"] or None,
            character_purpose=round_context["character_purpose"] or None,
            character_attitude=round_context["character_attitude"] or None,
            recent_conversations=recent_conv_snapshot,
            future_time_natural=step5_result.future.time_natural, future_action=step5_result.future.action,
            future_clear_slot=handle.slot)
        def confirmed():
            _spawn_effect(life.step6_effect(handle, lambda: execute_step6(step6_snapshot)), handle.consume_id)
            _spawn_effect(_normal_effects(handle, step5_result), handle.consume_id)
        score = await agent_service.calculate_action_score(user_id, TriggerType.FUTURE)
        return await life.commit_success(handle, effects.arm(confirmed), content=reply_text, score=score,
            success_kind='normal', round_id=round_id, on_success=effects.confirmed)
    except Exception:
        logger.exception('[Step8] 子链执行失败 user_id=%s', user_id)
        raise

async def _normal_effects(handle, step5_result):
    try:
        await _decay_gate_and_update(handle, step5_result)
    except Exception:
        logger.exception('future_normal_decay_failed consume=%s', handle.consume_id)
        await life.effect_failed(handle.user_id, handle.consume_id, 'normal_decay')
    try:
        await life.handler_effects(handle.user_id, handle.consume_id)
    except Exception:
        logger.exception('future_handler_effect_failed consume=%s', handle.consume_id)


# ================================================================
#  辅助函数
# ================================================================


async def _get_recent_conversations(
    user_id: int, db: AsyncSession,
) -> list[ConversationLog]:
    """获取最近 20 条对话"""
    stmt = (
        select(ConversationLog)
        .where(ConversationLog.user_id == user_id)
        .order_by(desc(ConversationLog.created_at))
        .limit(20)
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def _get_relationship(
    user_id: int, db: AsyncSession,
) -> Relationship | None:
    """获取关系信息"""
    stmt = select(Relationship).where(Relationship.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_emotion_context(
    user_id: int, db: AsyncSession,
) -> dict | None:
    """获取短期情绪上下文"""
    try:
        redis_conn = await get_redis()
        return await user_short_term_emotion_service.read_for_prompt(
            user_id, db, redis_conn,
        )
    except Exception:
        logger.warning("[Step8] 读取短期情绪失败: user_id=%d", user_id, exc_info=True)
        return None


def _build_step8_round_context(
    relationship_info: Relationship | None,
    time_description: str,
    activity_description: str,
) -> dict:
    """构建 Step8 子链路的 round_context（复用主链逻辑）"""
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

    def _safe(val, fallback=""):
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


def _check_persona_risk(text: str) -> bool:
    """检查人格风险关键词"""
    text_lower = text.lower()
    for _, keywords in PERSONA_RISK_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return True
    return False


async def _fallback_write_agent_message(handle, effects=None):
    """Independent fallback transaction carries exactly the same consumption fence."""
    effects = effects or _SuccessEffects()
    score = await agent_service.calculate_action_score(handle.user_id, TriggerType.FUTURE)
    def confirmed():
        _spawn_effect(life.handler_effects(handle.user_id, handle.consume_id))
    return await life.commit_success(handle, effects.arm(confirmed), content=STEP8_FALLBACK_REPLY,
        score=score, success_kind='fallback', round_id=str(uuid.uuid4()), on_success=effects.confirmed)

async def _decay_gate_and_update(handle, step5_result):
    async def apply(db, rel, row):
        if rel is None: return
        rel.proactive_times = min(3, rel.proactive_times+1)
        future_time = step5_result.future.time_natural
        future_action = step5_result.future.action
        if future_action and future_action != '无' and future_time and future_time != '无':
            probability = DECAY_BASE ** (rel.proactive_times+1)
            if random.random() < probability:
                parsed = parse_future_time(future_time)
                if parsed is not None:
                    rel.future_timestamp = parsed
                    rel.future_action = future_action
                    rel.future_slot_version += 1
    return await life.sql_effect(handle.user_id, handle.consume_id, 'normal_decay', apply)
