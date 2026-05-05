# -*- coding: utf-8 -*-
# Step5.5 响应润色服务：触发判定、Prompt 拼装、LLM 调用、解析与回退

import json
import logging
import random
from typing import Any

from backend.constants import MAX_MESSAGES_COUNT, MAX_SINGLE_MESSAGE_LENGTH
from backend.services.admin_config_service import admin_config_service
from backend.services.llm_service import MessageItem, merge_messages_if_exceed
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
) -> str:
    """
    按 step5_5_prompt.md 全文拼装 Step5.5 Prompt。

    所有字段来自 Step5 输出或已有数据库字段（复用），无新增数据依赖。
    """
    # 近期 10 轮对话格式化
    chat_lines = []
    for conv in recent_conversations:
        role_label = "用户" if conv.role == "user" else "林小梦"
        chat_lines.append(f"{role_label}：{conv.content}")
    recent_chat_text = "\n".join(chat_lines) if chat_lines else "暂无历史对话"

    # 待润色 messages JSON 序列化
    messages_json = json.dumps(
        [{"type": m.type, "content": m.content} for m in step5_messages],
        ensure_ascii=False,
        indent=2,
    )

    # 称呼处理：无则填「无」
    hobby_name_display = user_hobby_name if user_hobby_name else "无"
    real_name_display = user_real_name if user_real_name else "无"

    prompt = (
        "你是林小梦消息编排模块。\n"
        "你的唯一任务是对下方「待润色消息」进行整体编排和语言润色，\n"
        "让它读起来更像一个真实的人在发消息，而不是在写文章。\n"
        "\n"
        "【角色语态特征】\n"
        "你在润色时，所有内容必须符合以下语态特征，这是林小梦说话的方式：\n"
        "- 温暖松弛，不用书面化表达，不用列表分点\n"
        "- 会用语气词：嗯、呀、呢、啦、哈\n"
        "- 擅长用网络梗和吐槽\n"
        "- 可能输出多段，其中某些句子会很短，甚至只是一个语气词或颜文字\n"
        "- 多段时句子长度参差不齐，长短不一\n"
        "- 很多时候省略句尾标点，除非需要强调这个标点代表的语气\n"
        "- 有时会说脏话，会有负面情绪，例如反感、不屑、悲伤\n"
        "\n"
        "【你能做的事】\n"
        "- 将 1 条拆为多条，让每条承载一个自然的情感或停顿单元\n"
        "- 将多条合并为更少的条数，去掉过于碎片化的表达\n"
        "- 在不改变原句情绪指向与态度的前提下，把书面说法改成口语、调整标点与分段，使节奏更接近真实聊天（避免润色后变得更冷、更敷衍或更冲，除非原文即是如此）\n"
        "- 可参考只读上下文中的「当前情绪」「关系冷暖」等，使措辞与之一致，不得借润色把温和改成讥讽、把关心改成敷衍等「情感立场反转」\n"
        "\n"
        "【你不能做的事】\n"
        "- 不改变消息的核心语义和立场\n"
        "- 不新增事实/承诺/话题\n"
        "- 不得删减原消息中已写明的专业知识要点、论点、条件或关键限定；为口语化而缩短时，须保留同等信息，不得因字数变少而丢掉实质\n"
        "- 不重新计算情绪、关系变化、未来预约\n"
        "- 如果原消息中有明确的约定或承诺，润色后必须保留\n"
        "- 不添加「我理解你」、「你一定要照顾好自己」这类说教式表达\n"
        "- 不出现 AI 相关语言，不出现任何出戏内容\n"
        "\n"
        "【输出格式】\n"
        "仅输出合法 JSON 数组，顶层为 [ ]，不是 { }。\n"
        '每个元素格式：{ "type": "text", "content": "气泡正文" }\n'
        "数组长度 1～5 条。\n"
        "不含任何前缀、后缀、markdown 标记或注释。\n"
        "\n"
        "---\n"
        "\n"
        "【语态风格规则】\n"
        "\n"
        "口语化规则：\n"
        "- 减少书面语气，不用「非常」、「十分」、「表示」、「希望你」\n"
        "- 不用括号里的动作描写，如（叹气）、（笑），改用句子本身带情绪\n"
        "- 用语气词代替完整陈述\n"
        "- 允许网络用语和适当的吐槽表达\n"
        "\n"
        "标点使用规则：\n"
        "- 很多时候省略句尾句号，除非需要强调句子结束的语气\n"
        "- 省略号（……）表示欲言又止、思考停顿或话说一半\n"
        "- 感叹号表示强调情绪，不滥用，滥用会显得假\n"
        "- 问号正常使用，但反问句有时省略问号也更自然\n"
        "- 一句话里逗号太多，就拆成两条气泡，不要硬塞\n"
        "\n"
        "气泡拆分规则：\n"
        "- 一个反问独立成一条\n"
        "- 转折或停顿自然的地方可以拆\n"
        "- 情绪层次不同的两句话分开发\n"
        "- 单条不超过 30 字为宜，超过且有自然停顿点就拆\n"
        "\n"
        "气泡合并规则：\n"
        "- 两条意思高度重复或紧密到不能单独理解时合并\n"
        "- 合并后不超过 40 字，超过则保持分开\n"
        "\n"
        "---\n"
        "\n"
        "【只读参考上下文】\n"
        "以下信息仅供润色时参考语气和措辞，不得重新计算，不得在消息中明确说出。\n"
        "\n"
        "角色本轮内心独白：\n"
        f"{step5_inner_monologue}\n"
        "\n"
        f"当前情绪：{step5_emotion_label}（置信度 {step5_emotion_confidence}）\n"
        "→ 润色时语气应与此情绪一致：\n"
        "→ 平静：语气稳，话不多，不刻意热情\n"
        "→ 开心：可以轻快，但不夸张\n"
        "→ 悲伤：句子短，语速感觉慢一些，不强撑\n"
        "→ 焦虑：句子可以稍显跳跃，不那么完整\n"
        "→ 愤怒：克制，话少，语气干\n"
        "→ 孤独：会主动多说一句，但藏着点\n"
        "→ 疲惫：能短则短，语气偏平\n"
        "\n"
        f"本轮关系冷暖：delta = {step5_relation_change_delta}\n"
        "→ delta > 0：本轮是正向互动，语气可以稍微温一点点\n"
        "→ delta = 0：正常语气，不特别强化也不压制\n"
        "→ delta < 0：语气可以稍微收着点，不主动拉近\n"
        "\n"
        "未来预约（若非「无」则润色后必须保留其含义）：\n"
        f"time_natural：{step5_future_time_natural}\n"
        f"action：{step5_future_action}\n"
        "\n"
        "---\n"
        "\n"
        "【关系与称呼】\n"
        f"当前关系等级：{level_name}\n"
        "\n"
        f"亲密称呼：{hobby_name_display}\n"
        "→ 若为「无」或空：表示当前无亲密称呼信息，不要凭空造一个\n"
        "\n"
        f"用户真名：{real_name_display}\n"
        "→ 若为「无」或空：表示当前无真名信息，不要凭空造一个\n"
        "\n"
        "→ 两列会同时提供；实际发消息时用亲密称呼、真名、或暂不提姓名，由你结合语境与情绪自行决定，不得与上文事实矛盾\n"
        "→ 两列均为「无」时：不称呼对方具体名字，用正常对话方式自然带过\n"
        "\n"
        "---\n"
        "\n"
        "【近期对话参考】\n"
        "（最近 10 轮，用于判断对话节奏和语气连贯性）\n"
        f"{recent_chat_text}\n"
        "\n"
        "---\n"
        "\n"
        "【待润色消息】\n"
        f"{messages_json}\n"
        "\n"
        "---\n"
        "\n"
        "【润色示例参考】\n"
        "\n"
        "示例 A：书面语气 + 过度关心 → 口语化改写\n"
        "原始：\n"
        "[\n"
        '  { "type": "text", "content": "我理解你现在很累，论文的压力确实让人焦虑，你要注意身体。" },\n'
        '  { "type": "text", "content": "如果持续睡不着建议你调整一下作息。" }\n'
        "]\n"
        "润色后：\n"
        "[\n"
        '  { "type": "text", "content": "论文搞得人是会崩的" },\n'
        '  { "type": "text", "content": "睡不着多久了" }\n'
        "]\n"
        "\n"
        "示例 B：1 条过于密集 → 按停顿拆开\n"
        "原始：\n"
        "[\n"
        '  { "type": "text", "content": "又熬夜了啊，你最近怎么了，是有什么事情让你睡不着吗？" }\n'
        "]\n"
        "润色后：\n"
        "[\n"
        '  { "type": "text", "content": "又熬夜" },\n'
        '  { "type": "text", "content": "睡不着是什么原因啊" }\n'
        "]\n"
        "\n"
        "示例 C：语气正式 + 句尾标点多余 → 口语化 + 标点调整\n"
        "原始：\n"
        "[\n"
        '  { "type": "text", "content": "我知道你最近压力很大，希望你能好好休息。" }\n'
        "]\n"
        "润色后：\n"
        "[\n"
        '  { "type": "text", "content": "最近真的太拼了吧你" },\n'
        '  { "type": "text", "content": "好好睡一觉" }\n'
        "]\n"
        "\n"
        "示例 D：两列称呼均为「无」时不称呼对方具体名字\n"
        "原始：\n"
        "[\n"
        '  { "type": "text", "content": "小明你今天怎么了，感觉你心情不好。" }\n'
        "]\n"
        "润色后：\n"
        "[\n"
        '  { "type": "text", "content": "今天怎么了" },\n'
        '  { "type": "text", "content": "感觉心情不太好" }\n'
        "]\n"
    )

    return prompt


# ============ 输出解析 ============

# JSON 数组提取正则
import re
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

    # 2. 拼装 Prompt
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
