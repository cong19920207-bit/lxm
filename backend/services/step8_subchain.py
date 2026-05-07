# -*- coding: utf-8 -*-
# Step8 子链路：Future 槽到期触发的主动消息生成，复用主链 Step 变体

import asyncio
import logging
import random
import uuid
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_llm_timeout_chat_seconds
from backend.constants import PERSONA_RISK_KEYWORDS
from backend.database import async_session_maker
from backend.models.agent_message import AgentMessage, TriggerType
from backend.models.conversation_log import ConversationLog
from backend.models.emotion_log import EmotionLog
from backend.models.relationship import Relationship
from backend.redis_client import get_redis
from backend.services.content_safety_service import check_content
from backend.services.llm_service import (
    Step5ParseError,
    llm_service,
    merge_messages_if_exceed,
)
from backend.services.multi_vector_retrieval_service import execute_multi_vector_retrieval
from backend.services.prompt_builder import (
    DEFAULT_PERSONA,
    LEVEL_DEFINITIONS,
    REDIS_KEY_PERSONA,
    PromptBuilder,
    _generate_time_description,
    get_activity_description,
)
from backend.services.query_rewrite_service import execute_query_rewrite
from backend.services.step5_5_service import execute_step5_5
from backend.services.step6_orchestrator import Step6Snapshot, execute_step6
from backend.services.timeline_seq_service import allocate_sort_seq
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


async def execute_step8_subchain(user_id: int, future_action: str | None) -> bool:
    """
    Step8 子链路完整执行：Future 槽到期触发的主动消息生成。

    子链路步骤：
    1. Step1：并行装载上下文（recent_conversations, relationship, emotion）
    2. Step1.5 变体：查询重写（输入用 future.action 替代 last_user_text）
    3. Step2：多路向量检索（完全复用）
    4. Step3 变体：Prompt 拼装（模块9 替换为【主动发起】）
    5. Step5：LLM 调用（Schema 一致，完全复用）
    6. Step5.5：可配置较低触发概率
    7. 产出写入 agent_message 表（不走 SSE）
    8. Step6：记忆总结（完全复用）
    9. proactive_times +1；衰减门控

    Args:
        user_id: 用户 ID
        future_action: Future 槽意图摘要

    Returns:
        True=执行成功, False=失败
    """
    # future_action 为空时整轮失败
    if not future_action or not future_action.strip():
        logger.error(
            "[Step8] future_action 为空，整轮主动消息失败: user_id=%d", user_id
        )
        return False

    try:
        # ── Step1：并行装载上下文 ──
        logger.info("[Step8] 开始子链路: user_id=%d, action=%s", user_id, future_action)

        # 同一 AsyncSession 禁止并发查询（asyncio.gather 会触发连接状态冲突）
        async with async_session_maker() as db:
            recent_conversations = await _get_recent_conversations(user_id, db)
            relationship_info = await _get_relationship(user_id, db)
            emotion_context = await _get_emotion_context(user_id, db)

        recent_10 = recent_conversations[-10:] if len(recent_conversations) > 10 else recent_conversations

        # 构建本轮内存上下文
        time_description = _generate_time_description()
        activity_description = await get_activity_description()
        round_context = _build_step8_round_context(
            relationship_info, time_description, activity_description,
        )

        # ── Step1.5 变体：用 future.action 替代 last_user_text ──
        r_for_persona = await get_redis()
        persona_text = await r_for_persona.get(REDIS_KEY_PERSONA)
        if not persona_text:
            persona_text = DEFAULT_PERSONA

        query_rewrite_result = await execute_query_rewrite(
            user_id=user_id,
            last_user_text=future_action,
            persona_text=persona_text,
            round_context=round_context,
            recent_conversations=recent_10,
            source="step8",
        )

        # ── Step2：多路向量检索（完全复用）──
        retrieval_result = await execute_multi_vector_retrieval(
            query_rewrite_result=query_rewrite_result,
            user_id=user_id,
        )

        memories_raw = retrieval_result.user_memory_results
        retrieval_for_prompt = retrieval_result.format_for_prompt()

        # ── Step3 变体：Prompt 拼装（模块9 替换为【主动发起】）──
        async with async_session_maker() as db:
            builder = PromptBuilder(db)
            prompt = await builder.build_step8_prompt(
                user_id=user_id,
                future_action=future_action,
                memories=memories_raw,
                recent_conversations=recent_10,
                relationship_info=relationship_info,
                emotion_context=emotion_context,
                round_context=round_context,
                retrieval_results=retrieval_for_prompt,
            )

        # ── Step5：LLM 调用（Schema 一致）──
        try:
            step5_result = await llm_service.chat_with_step5_parse(
                prompt,
                timeout_sec=get_llm_timeout_chat_seconds(),
            )
        except (Step5ParseError, Exception) as e:
            logger.error("[Step8] Step5 LLM 失败: user_id=%d, error=%s", user_id, e)
            return False

        # 内容安全检测：messages 逐条
        for idx, msg in enumerate(step5_result.messages):
            content = msg.content if hasattr(msg, "content") else ""
            if content and content.strip():
                safety = await check_content(content)
                if not safety["is_safe"]:
                    logger.warning(
                        "[Step8] Step5 messages[%d] 内容安全拦截: user_id=%d", idx, user_id
                    )
                    return False

        # 人格风险关键词扫描
        for msg in step5_result.messages:
            if _check_persona_risk(msg.content):
                logger.warning(
                    "[Step8] 人格风险检测命中，使用兜底: user_id=%d", user_id
                )
                return await _fallback_write_agent_message(user_id)

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
        emotion_data = {
            "label": step5_result.emotion.label,
            "confidence": step5_result.emotion.confidence,
        }

        async with async_session_maker() as db:
            score = await agent_service.calculate_action_score(user_id, TriggerType.FUTURE)

            seqs = await allocate_sort_seq(user_id, count=1, db=db)
            agent_msg = AgentMessage(
                user_id=user_id,
                trigger_type=TriggerType.FUTURE,
                content=reply_text,
                action_score=score,
                sort_seq=seqs[0],
            )
            db.add(agent_msg)
            await db.commit()
            logger.info(
                "[Step8] agent_message 写入成功: user_id=%d, sort_seq=%d",
                user_id, seqs[0],
            )

        # ── Step6：记忆总结（完全复用，异步不阻塞）──
        try:
            recent_conv_snapshot = [
                {"role": c.role, "content": c.content} for c in recent_10
            ]
            step6_snapshot = Step6Snapshot(
                user_id=user_id,
                round_id=round_id,
                step6_messages=step6_messages,
                user_input=future_action,
                persona_text=persona_text,
                level_name=level_name,
                relation_description=round_context["relation_description"] or None,
                user_real_name=round_context["user_real_name"] or None,
                user_hobby_name=round_context["user_hobby_name"] or None,
                user_description=round_context["user_description"] or None,
                character_purpose=round_context["character_purpose"] or None,
                character_attitude=round_context["character_attitude"] or None,
                recent_conversations=recent_conv_snapshot,
                future_time_natural=step5_result.future.time_natural,
                future_action=step5_result.future.action,
            )
            asyncio.create_task(execute_step6(step6_snapshot))
        except Exception:
            logger.exception("[Step8] Step6 入队失败(不影响主流程): user_id=%d", user_id)

        # ── proactive_times +1 + 衰减门控 ──
        await _decay_gate_and_update(user_id, step5_result)

        logger.info("[Step8] 子链路完成: user_id=%d, round_id=%s", user_id, round_id)
        return True

    except Exception as e:
        logger.error(
            "[Step8] 子链路异常: user_id=%d, error=%s", user_id, str(e), exc_info=True
        )
        return False


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


async def _fallback_write_agent_message(user_id: int) -> bool:
    """人格风险触发时写入兜底 agent_message"""
    try:
        async with async_session_maker() as db:
            score = await agent_service.calculate_action_score(user_id, TriggerType.FUTURE)
            seqs = await allocate_sort_seq(user_id, count=1, db=db)
            agent_msg = AgentMessage(
                user_id=user_id,
                trigger_type=TriggerType.FUTURE,
                content=STEP8_FALLBACK_REPLY,
                action_score=score,
                sort_seq=seqs[0],
            )
            db.add(agent_msg)
            await db.commit()
        return True
    except Exception:
        logger.exception("[Step8] 兜底写入失败: user_id=%d", user_id)
        return False


async def _decay_gate_and_update(user_id: int, step5_result) -> None:
    """
    proactive_times +1 + 衰减门控：
    以 0.15^(proactive_times+1) 概率决定是否写入下一轮 Future 预约。
    """
    try:
        async with async_session_maker() as db:
            stmt = select(Relationship).where(Relationship.user_id == user_id)
            result = await db.execute(stmt)
            rel = result.scalar_one_or_none()
            if rel is None:
                return

            # proactive_times +1（上限 3）
            old_pt = rel.proactive_times
            if rel.proactive_times < 3:
                rel.proactive_times += 1

            new_pt = rel.proactive_times

            # 衰减门控：检查 Step5 是否输出了新的 Future
            future_time = step5_result.future.time_natural
            future_action = step5_result.future.action

            if future_action and future_action != "无" and future_time and future_time != "无":
                # 以 0.15^(proactive_times+1) 概率写入
                probability = DECAY_BASE ** (new_pt + 1)
                roll = random.random()

                if roll < probability:
                    # 命中：解析时间并写入 Future 槽
                    parsed_ts = parse_future_time(future_time)
                    if parsed_ts is not None:
                        rel.future_timestamp = parsed_ts
                        rel.future_action = future_action
                        logger.info(
                            "[Step8] 衰减门控命中，写入下一轮 Future: "
                            "user_id=%d, pt=%d, prob=%.6f, roll=%.6f, ts=%d",
                            user_id, new_pt, probability, roll, parsed_ts,
                        )
                    else:
                        logger.warning(
                            "[Step8] 衰减门控命中但时间解析失败: "
                            "user_id=%d, time_natural=%s",
                            user_id, future_time,
                        )
                else:
                    # 未命中：不写入
                    logger.info(
                        "[Step8] 衰减门控未命中: "
                        "user_id=%d, pt=%d, prob=%.6f, roll=%.6f",
                        user_id, new_pt, probability, roll,
                    )
            else:
                logger.debug(
                    "[Step8] Step5 未输出有效 Future: user_id=%d", user_id
                )

            await db.commit()
            logger.info(
                "[Step8] proactive_times 更新: user_id=%d, %d→%d",
                user_id, old_pt, new_pt,
            )
    except Exception:
        logger.exception("[Step8] 衰减门控/proactive_times 更新失败: user_id=%d", user_id)
