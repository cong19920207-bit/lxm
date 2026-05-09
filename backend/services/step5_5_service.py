# -*- coding: utf-8 -*-
# Step5.5 响应润色服务：触发判定、Prompt 拼装、LLM 调用、解析与回退

import json
import logging
import random
import re
from typing import Any

from backend.constants import MAX_MESSAGES_COUNT, MAX_SINGLE_MESSAGE_LENGTH
from backend.services.admin_config_service import admin_config_service
from backend.services.llm_service import MessageItem, merge_messages_if_exceed
from backend.services.step5_5_prompt_fragments import (
    assemble_step5_5_prompt_text,
    merge_step5_5_fragments,
)
from backend.utils.llm_client import llm_client

logger = logging.getLogger(__name__)

# Step5.5 独立子超时（§2.7.4 D2）
STEP5_5_TIMEOUT_SEC = 30.0

# 门闩 A 概率（§2.7.1）
GATE_A_PROBABILITY = 0.12

# 门闩 B 概率（仅 knowledge_expand == "是" 时生效）
GATE_B_PROBABILITY = 0.5

# admin_config 总开关键名
STEP5_5_SWITCH_CONFIG_KEY = "step5_5_enabled"

# Step5.5 模板片段（六段 JSON）
STEP5_5_FRAGMENTS_CONFIG_KEY = "step5_5_prompt_fragments"


# ============ 触发判定 ============


async def should_trigger_step5_5(
    knowledge_expand: str,
    *,
    gate_a_override: float | None = None,
    _rand_a: float | None = None,
    _rand_b: float | None = None,
) -> bool:
    """
    Step5.5 双门闩 OR 触发判定。

    1. 读 admin_config 总开关（B3），关闭则直接返回 False
    2. 门闩 A：rand < gate_a_probability（默认 12%，可通过 gate_a_override 覆盖）
    3. 门闩 B：仅当 knowledge_expand == "是" 时，rand < 0.5（独立 50%）
    4. 命中 A OR B → True

    Args:
        knowledge_expand: Step5 输出的 knowledge_expand 字段
        gate_a_override: 覆盖门闩 A 概率（Step8 子链路用较低值）
        _rand_a: 测试注入用，覆盖门闩 A 的随机数
        _rand_b: 测试注入用，覆盖门闩 B 的随机数

    Returns:
        是否触发 Step5.5
    """
    # 总开关检查
    switch_value = await admin_config_service.get_active_config(STEP5_5_SWITCH_CONFIG_KEY)
    if not _is_switch_on(switch_value):
        logger.debug("Step5.5 总开关关闭，跳过")
        return False

    # 门闩 A：默认 12%，Step8 子链路可传入较低值
    gate_a_prob = gate_a_override if gate_a_override is not None else GATE_A_PROBABILITY
    rand_a = _rand_a if _rand_a is not None else random.random()
    gate_a = rand_a < gate_a_prob

    # 门闩 B：仅 knowledge_expand == "是" 时独立 50%
    gate_b = False
    if knowledge_expand == "是":
        rand_b = _rand_b if _rand_b is not None else random.random()
        gate_b = rand_b < GATE_B_PROBABILITY

    triggered = gate_a or gate_b

    if triggered:
        logger.info(
            "Step5.5 触发: gate_a=%s(rand=%.4f, prob=%.4f) gate_b=%s(ke=%s)",
            gate_a, rand_a, gate_a_prob, gate_b, knowledge_expand,
        )

    return triggered


def _is_switch_on(value: Any) -> bool:
    """判断总开关是否开启，支持多种值类型"""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "on", "yes", "enabled")
    if isinstance(value, dict):
        return _is_switch_on(value.get("enabled", value.get("value", False)))
    return False


# ============ Prompt 拼装 ============


def build_step5_5_prompt(
    *,
    step5_inner_monologue: str,
    step5_emotion_label: str,
    step5_emotion_confidence: float,
    step5_relation_change_delta: int,
    step5_future_time_natural: str,
    step5_future_action: str,
    step5_messages: list[MessageItem],
    level_name: str,
    user_hobby_name: str | None,
    user_real_name: str | None,
    recent_conversations: list,
    fragments: dict[str, str] | None = None,
) -> str:
    """
    按 step5_5_prompt.md 全文拼装 Step5.5 Prompt。

    fragments：管理后台发布的六段模板；None 时使用内置默认（与历史硬编码一致）。
    """
    chat_lines = []
    for conv in recent_conversations:
        role_label = "用户" if conv.role == "user" else "林小梦"
        chat_lines.append(f"{role_label}：{conv.content}")
    recent_chat_text = "\n".join(chat_lines) if chat_lines else "暂无历史对话"

    messages_json = json.dumps(
        [{"type": m.type, "content": m.content} for m in step5_messages],
        ensure_ascii=False,
        indent=2,
    )

    hobby_name_display = user_hobby_name if user_hobby_name else "无"
    real_name_display = user_real_name if user_real_name else "无"

    merged_fragments = merge_step5_5_fragments(fragments)

    return assemble_step5_5_prompt_text(
        merged_fragments,
        inner_monologue=step5_inner_monologue,
        emotion_label=step5_emotion_label,
        emotion_confidence=step5_emotion_confidence,
        relation_delta=step5_relation_change_delta,
        future_time_natural=step5_future_time_natural,
        future_action=step5_future_action,
        level_name=level_name,
        user_hobby_display=hobby_name_display,
        user_real_name_display=real_name_display,
        recent_chat_text=recent_chat_text,
        messages_json=messages_json,
    )


async def load_active_step5_5_fragments() -> dict[str, str]:
    """读取当前生效 Step5.5 片段（admin_config + 默认合并）。"""
    raw = await admin_config_service.get_active_config(STEP5_5_FRAGMENTS_CONFIG_KEY)
    if isinstance(raw, dict):
        return merge_step5_5_fragments(raw)
    return merge_step5_5_fragments(None)


# ============ 输出解析 ============

# JSON 数组提取正则
_JSON_ARRAY_PATTERN = re.compile(r"\[[\s\S]*\]")


def parse_step5_5_output(raw_text: str) -> list[MessageItem]:
    """
    解析 Step5.5 LLM 输出为 MessageItem 列表。

    校验规则：
    - 必须为合法 JSON 数组
    - 每条 type 精确等于 "text"（大小写敏感）
    - 每条 content 非空（trim 后）

    Raises:
        ValueError: 解析或校验失败
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Step5.5 LLM 返回空文本")

    text = raw_text.strip()

    # 尝试提取 JSON 数组
    match = _JSON_ARRAY_PATTERN.search(text)
    if match:
        text = match.group()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Step5.5 JSON 解析失败: {e}") from e

    if not isinstance(data, list):
        raise ValueError(f"Step5.5 输出顶层不是数组，类型为 {type(data).__name__}")

    if len(data) == 0:
        raise ValueError("Step5.5 输出为空数组")

    messages: list[MessageItem] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Step5.5 messages[{i}] 不是对象")

        msg_type = item.get("type")
        if msg_type != "text":
            raise ValueError(
                f'Step5.5 messages[{i}].type="{msg_type}" 非精确 "text"'
            )

        content = item.get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"Step5.5 messages[{i}].content 为空")

        messages.append(MessageItem(type="text", content=content))

    return messages


# ============ 完整执行链路 ============


async def execute_step5_5(
    *,
    step5_messages: list[MessageItem],
    step5_inner_monologue: str,
    step5_emotion_label: str,
    step5_emotion_confidence: float,
    step5_relation_change_delta: int,
    step5_future_time_natural: str,
    step5_future_action: str,
    step5_knowledge_expand: str,
    level_name: str,
    user_hobby_name: str | None,
    user_real_name: str | None,
    recent_conversations: list,
    gate_a_override: float | None = None,
) -> list[MessageItem] | None:
    """
    Step5.5 完整执行链路。

    1. 触发判定（总开关 + 双门闩 OR）
    2. 拼装 Prompt
    3. LLM 调用（timeout=30s，无重试 — 独立子超时）
    4. 解析输出
    5. 成功 → 合并至 ≤5 条后返回
    6. 失败/超时 → 返回 None（调用方使用 Step5 原始 messages）

    Args:
        step5_*: Step5 输出的各字段
        level_name: 关系等级名称
        user_hobby_name: 亲密称呼
        user_real_name: 用户真名
        recent_conversations: 最近 10 轮对话
        gate_a_override: 覆盖门闩 A 概率（Step8 子链路传入较低值，如 0.03）

    Returns:
        润色后的 MessageItem 列表（已合并至 ≤5 条），或 None 表示未触发/失败
    """
    # 1. 触发判定
    triggered = await should_trigger_step5_5(
        step5_knowledge_expand, gate_a_override=gate_a_override,
    )
    if not triggered:
        return None

    # 2. 拼装 Prompt（热加载 admin_config 六段模板）
    fragments_loaded = await load_active_step5_5_fragments()
    prompt = build_step5_5_prompt(
        step5_inner_monologue=step5_inner_monologue,
        step5_emotion_label=step5_emotion_label,
        step5_emotion_confidence=step5_emotion_confidence,
        step5_relation_change_delta=step5_relation_change_delta,
        step5_future_time_natural=step5_future_time_natural,
        step5_future_action=step5_future_action,
        step5_messages=step5_messages,
        level_name=level_name,
        user_hobby_name=user_hobby_name,
        user_real_name=user_real_name,
        recent_conversations=recent_conversations,
        fragments=fragments_loaded,
    )

    # 3. LLM 调用（独立子超时 30s，不走 llm_service 的重试 —— chat_sync 内部已含重试）
    try:
        import asyncio
        raw_text = await asyncio.wait_for(
            llm_client.chat_sync(prompt, timeout_sec=STEP5_5_TIMEOUT_SEC),
            timeout=STEP5_5_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        logger.warning("Step5.5 LLM 调用超时（%.0fs），回退 Step5", STEP5_5_TIMEOUT_SEC)
        return None
    except Exception as e:
        logger.error("Step5.5 LLM 调用失败: %s，回退 Step5", e)
        return None

    # 4. 解析输出
    try:
        parsed_messages = parse_step5_5_output(raw_text)
    except ValueError as e:
        logger.warning("Step5.5 解析失败: %s，回退 Step5", e)
        return None

    # 5. 合并至 ≤5 条（复用 STEP-006 合并规则）
    merged = merge_messages_if_exceed(parsed_messages)

    logger.info(
        "Step5.5 执行成功: 原 %d 条 → 润色 %d 条 → 合并 %d 条",
        len(step5_messages), len(parsed_messages), len(merged),
    )

    return merged
