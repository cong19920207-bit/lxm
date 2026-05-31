# -*- coding: utf-8 -*-
# Step6 异步编排器：M2 半异步，不阻塞 SSE；失败重试 1 次（共 2 次尝试）

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select

from backend.database import async_session_maker
from backend.models.relationship import Relationship
from backend.services.llm_service import MessageItem
from backend.services.memory_llm_service import (
    Step6ParseError,
    build_step6_prompt,
    parse_step6_output,
    upsert_step6_vectors,
)
from backend.services.relationship_service import RelationshipService
from backend.utils.llm_client import llm_client

logger = logging.getLogger(__name__)

# M2 重试退避时间（§2.8.4：200ms～1s，默认 500ms）
_RETRY_BACKOFF_SEC = 0.5

# Step6 LLM 单次超时（固定 45s，与主链 Step5 默认 LLM_TIMEOUT_CHAT 对齐；非环境变量）
_STEP6_LLM_TIMEOUT_SEC = 45.0


@dataclass
class Step6Snapshot:
    """
    Step6 入参快照：在 Step5 成功后一次性捕获，确保 Step6 仅基于 Step5 产出。

    messages 已经过 STEP-006 合并至 ≤5 条（CP1）；
    不使用 Step5.5 润色后版本（R-BND-05）。
    """
    user_id: int
    round_id: str
    step6_messages: list  # list[MessageItem]
    user_input: str
    persona_text: str
    level_name: str
    relation_description: Optional[str] = None
    user_real_name: Optional[str] = None
    user_hobby_name: Optional[str] = None
    user_description: Optional[str] = None
    character_purpose: Optional[str] = None
    character_attitude: Optional[str] = None
    recent_conversations: list = field(default_factory=list)  # list[dict{role, content}]
    future_time_natural: str = "无"
    future_action: str = "无"


@dataclass
class _ConvProxy:
    """轻量代理对象，供 build_step6_prompt 使用（需 .role / .content 属性）。"""
    role: str
    content: str


async def execute_step6(snapshot: Step6Snapshot) -> None:
    """
    Step6 异步任务入口：M2 半异步，不阻塞 SSE。

    调用链：记忆 LLM → 向量写入（STEP-014）→ 标量+Future 更新（STEP-015）
    重试策略：首次失败 → sleep 500ms → 重试一次 → 仍失败则写日志，任务结束。
    """
    for attempt in range(2):
        try:
            await _step6_pipeline(snapshot)
            logger.info(
                "Step6 完成: user_id=%d, round_id=%s, attempt=%d",
                snapshot.user_id, snapshot.round_id, attempt + 1,
            )
            return
        except Exception as e:
            if attempt == 0:
                logger.warning(
                    "Step6 首次失败(将重试): user_id=%d, round_id=%s, error=%s",
                    snapshot.user_id, snapshot.round_id, str(e),
                )
                await asyncio.sleep(_RETRY_BACKOFF_SEC)
            else:
                # 重试后仍失败 → 允许不落库，不影响客户端
                logger.error(
                    "Step6 重试后仍失败(放弃): user_id=%d, round_id=%s, error=%s",
                    snapshot.user_id, snapshot.round_id, str(e),
                    exc_info=True,
                )


async def _step6_pipeline(snapshot: Step6Snapshot) -> None:
    """Step6 完整管线：Prompt 拼装 → LLM → 解析 → 向量写入 → 标量更新。"""

    # 1. 构建代理对象给 build_step6_prompt
    conv_proxies = [_ConvProxy(role=c["role"], content=c["content"]) for c in snapshot.recent_conversations]

    # 2. 拼装 Step6 Prompt（异步：内部读取 step6_memory_prompt 热配置）
    prompt = await build_step6_prompt(
        persona_text=snapshot.persona_text,
        level_name=snapshot.level_name,
        relation_description=snapshot.relation_description,
        user_real_name=snapshot.user_real_name,
        user_hobby_name=snapshot.user_hobby_name,
        user_description=snapshot.user_description,
        character_purpose=snapshot.character_purpose,
        character_attitude=snapshot.character_attitude,
        recent_conversations=conv_proxies,
        step5_messages=snapshot.step6_messages,
        user_input=snapshot.user_input,
    )

    # 3. 调用 LLM（非流式，timeout=_STEP6_LLM_TIMEOUT_SEC，默认 45s）
    raw_output = await llm_client.chat_sync(prompt, timeout_sec=_STEP6_LLM_TIMEOUT_SEC)

    # 4. 解析 Step6 JSON 输出
    step6_output = parse_step6_output(raw_output)

    # 5. 四路向量写入（STEP-014）
    await upsert_step6_vectors(step6_output, snapshot.user_id)

    # 6. 标量字段 + Future 槽更新（STEP-015）
    async with async_session_maker() as db:
        stmt = select(Relationship).where(Relationship.user_id == snapshot.user_id)
        result = await db.execute(stmt)
        relationship = result.scalar_one_or_none()

        if relationship is None:
            logger.warning(
                "Step6 标量更新跳过: 用户无 relationship 记录, user_id=%d",
                snapshot.user_id,
            )
            return

        svc = RelationshipService(db)
        await svc.update_relationship_from_step6(
            relationship=relationship,
            step6_output=step6_output,
            round_id=snapshot.round_id,
            future_time_natural=snapshot.future_time_natural,
            future_action=snapshot.future_action,
        )
        await db.commit()
