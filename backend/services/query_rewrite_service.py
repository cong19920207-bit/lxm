# -*- coding: utf-8 -*-
# Step1.5 查询重写 LLM 服务：分析用户意图，生成 3 组检索 QueryQuestion/Keywords
# 需求来源：R-L1L3-09 / R-L1L3-12 / R-L1L3-13 / R-L1L3-14

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field

from pydantic import BaseModel

from backend.services.embedding_service import embedding_service
from backend.utils.llm_client import llm_client

logger = logging.getLogger(__name__)

# Step1.5 专用超时（R-L1L3-13：timeout=15s）
_STEP1_5_TIMEOUT_SEC = 15.0
# R-L1L3-13：retry=1（共 2 次尝试），退避 500ms
_STEP1_5_MAX_ATTEMPTS = 2
_STEP1_5_RETRY_DELAY_SEC = 0.5

# JSON 提取正则：匹配第一个 { ... } 块（支持嵌套）
_JSON_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")


# ============ 输出模型（R-L1L3-09）============


class QueryRewriteOutput(BaseModel):
    """Step1.5 LLM 输出的 7 字段结构化模型"""
    InnerMonologue: str = ""
    CharacterGlobalQueryQuestion: str = ""
    CharacterGlobalQueryKeywords: str = ""
    CharacterKnowledgeQueryQuestion: str = ""
    CharacterKnowledgeQueryKeywords: str = ""
    UserProfileQueryQuestion: str = ""
    UserProfileQueryKeywords: str = ""


@dataclass
class QueryRewriteResult:
    """Step1.5 执行结果，供 Step2 消费"""
    success: bool
    output: QueryRewriteOutput | None = None
    # 降级时由 embedding_service 生成的单 Embedding（R-L1L3-12）
    fallback_embedding: list[float] = field(default_factory=list)


# ============ Prompt 拼装 ============


def _build_step1_5_prompt(
    *,
    persona_text: str,
    round_context: dict,
    recent_conversations: list,
    user_input: str,
) -> str:
    """
    拼装 Step1.5 查询重写 Prompt。

    模块结构：系统指令 + 时间活动 + 人格 + 关系 + 近期对话 + 用户消息 + 任务。
    复用 round_context 中已预计算的时间/活动/关系字段（R-L1L3-14）。
    """
    parts: list[str] = []

    # 系统指令
    parts.append(
        "【系统指令】\n"
        "你是林小梦，请根据用户最新消息，分析你的内心理解，并为记忆检索生成查询语句。\n"
        "输出格式要求：仅输出 JSON，不含任何额外内容、前缀、后缀或 markdown 标记。"
    )

    # 时间与状态
    time_desc = round_context.get("time_description", "")
    activity_desc = round_context.get("activity_description", "")
    if time_desc or activity_desc:
        time_parts = ["【当前时间与状态】"]
        if time_desc:
            time_parts.append(time_desc)
        if activity_desc:
            time_parts.append(activity_desc)
        parts.append("\n".join(time_parts))

    # 人格设定
    parts.append(f"【人格设定】\n{persona_text}")

    # 关系状态
    level_name = round_context.get("level_name", "陌生")
    relation_desc = round_context.get("relation_description", "暂无，初次互动")
    user_real_name = round_context.get("user_real_name", "")
    user_hobby_name = round_context.get("user_hobby_name", "")
    rel_lines = [
        "【关系状态】",
        f"当前关系等级：{level_name}",
        f"关系描述：{relation_desc}",
    ]
    # 优先展示亲密称呼，其次真实姓名
    call_name = user_hobby_name or user_real_name
    if call_name:
        rel_lines.append(f"用户称呼：{call_name}")
    parts.append("\n".join(rel_lines))

    # 近期对话（R-L1L3-14：最近 10 轮，复用已截取的 recent_10）
    if recent_conversations:
        chat_lines = ["【近期对话】"]
        for conv in recent_conversations:
            # 兼容 dict（snapshot）和 ORM 实例两种格式
            if isinstance(conv, dict):
                role = conv.get("role", "user")
                content = conv.get("content", "")
            else:
                role = conv.role
                content = conv.content
            role_label = "用户" if role == "user" else "林小梦"
            chat_lines.append(f"{role_label}：{content}")
        parts.append("\n".join(chat_lines))

    # 用户当前消息
    parts.append(f"【用户当前消息】\n{user_input}")

    # 任务 + 输出 Schema
    parts.append(
        "【任务】\n"
        "根据以上内容，输出以下 JSON（字段名区分大小写，严格遵守）：\n"
        "{\n"
        '  "InnerMonologue": "你对用户消息的内心理解，不超过100字",\n'
        '  "CharacterGlobalQueryQuestion": "用于检索角色背景设定的自然语言问题",\n'
        '  "CharacterGlobalQueryKeywords": "关键词1 关键词2 ...",\n'
        '  "CharacterKnowledgeQueryQuestion": "用于检索角色知识技能的自然语言问题",\n'
        '  "CharacterKnowledgeQueryKeywords": "关键词1 关键词2 ...",\n'
        '  "UserProfileQueryQuestion": "用于检索用户相关记忆的自然语言问题",\n'
        '  "UserProfileQueryKeywords": "关键词1 关键词2 ..."\n'
        "}"
    )

    return "\n\n".join(parts)


# ============ JSON 解析 ============


def _parse_query_rewrite_output(raw_text: str) -> QueryRewriteOutput:
    """
    解析 LLM 返回的 Step1.5 JSON 字符串。

    解析失败或关键字段全为空时抛 ValueError。
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("LLM 返回空文本")

    json_str = raw_text.strip()
    match = _JSON_PATTERN.search(json_str)
    if match:
        json_str = match.group()

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Step1.5 JSON 解析失败: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Step1.5 JSON 顶层不是对象")

    try:
        result = QueryRewriteOutput(**data)
    except Exception as e:
        raise ValueError(f"Step1.5 Pydantic 校验失败: {e}") from e

    # 3 组 QueryQuestion 至少有一组非空
    has_any = (
        result.CharacterGlobalQueryQuestion.strip()
        or result.CharacterKnowledgeQueryQuestion.strip()
        or result.UserProfileQueryQuestion.strip()
    )
    if not has_any:
        raise ValueError("Step1.5 三组 QueryQuestion 全部为空")

    return result


# ============ 核心调用入口 ============


async def execute_query_rewrite(
    *,
    user_id: int,
    last_user_text: str,
    persona_text: str,
    round_context: dict,
    recent_conversations: list,
    source: str = "main",
) -> QueryRewriteResult:
    """
    执行 Step1.5 查询重写 LLM。

    正常路径：LLM 输出 3 组 QueryQuestion/Keywords + InnerMonologue。
    失败路径：首次失败 → 退避 500ms → 重试 → 仍失败 → 降级。
    降级路径（R-L1L3-12）：用 last_user_text 生成单 Embedding 作为统一 fallback。

    Args:
        user_id: 用户 ID
        last_user_text: 用户最后一条消息（降级时用于生成 fallback Embedding）
        persona_text: 人格设定文本
        round_context: STEP-018 本轮内存上下文
        recent_conversations: 最近 10 轮对话（ORM 实例或 dict 列表）
        source: 链路来源标识，"main" 主链路 / "step8" Step8 子链路

    Returns:
        QueryRewriteResult，success=True 时 output 非空，
        success=False 时 fallback_embedding 非空（降级成功）或为空（降级也失败）
    """
    prompt = _build_step1_5_prompt(
        persona_text=persona_text,
        round_context=round_context,
        recent_conversations=recent_conversations,
        user_input=last_user_text,
    )

    last_error: str = ""

    for attempt in range(_STEP1_5_MAX_ATTEMPTS):
        if attempt > 0:
            await asyncio.sleep(_STEP1_5_RETRY_DELAY_SEC)

        start_time = time.monotonic()
        try:
            raw_text = await llm_client.chat_sync(
                prompt, timeout_sec=_STEP1_5_TIMEOUT_SEC
            )
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            output = _parse_query_rewrite_output(raw_text)

            logger.info(
                "Step1.5 查询重写成功: user_id=%d attempt=%d elapsed=%dms source=%s",
                user_id, attempt + 1, elapsed_ms, source,
            )
            return QueryRewriteResult(success=True, output=output)

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            last_error = str(e)
            logger.warning(
                "Step1.5 查询重写失败: user_id=%d attempt=%d/%d "
                "elapsed=%dms error=%s source=%s",
                user_id, attempt + 1, _STEP1_5_MAX_ATTEMPTS,
                elapsed_ms, last_error, source,
            )

    # 两次均失败 → 降级（R-L1L3-12）
    logger.error(
        "Step1.5 查询重写最终失败，启动降级: user_id=%d "
        "last_error=%s source=%s",
        user_id, last_error, source,
    )

    return await _fallback_with_embedding(
        user_id=user_id,
        text=last_user_text,
        last_error=last_error,
        source=source,
    )


async def _fallback_with_embedding(
    *,
    user_id: int,
    text: str,
    last_error: str,
    source: str,
) -> QueryRewriteResult:
    """
    降级路径：用 text 生成单 Embedding，传入 Step2 作为全部 4 路检索的统一 query。

    R-L1L3-12：失败不触发叹号，用户侧无感知。
    """
    try:
        fallback_emb = await embedding_service.get_embedding(text)
        logger.info(
            "Step1.5 降级 Embedding 生成成功: user_id=%d dim=%d source=%s",
            user_id, len(fallback_emb) if fallback_emb else 0, source,
        )
        return QueryRewriteResult(
            success=False,
            fallback_embedding=fallback_emb,
        )
    except Exception as emb_err:
        logger.error(
            "Step1.5 降级 Embedding 也失败: user_id=%d "
            "llm_error=%s emb_error=%s source=%s",
            user_id, last_error, str(emb_err), source,
        )
        return QueryRewriteResult(success=False, fallback_embedding=[])
