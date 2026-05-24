# -*- coding: utf-8 -*-
# Step6 记忆总结 LLM 服务：Prompt 拼装、结构化 JSON 解析（11 字段驼峰）、四路向量写入

import json
import logging
import re
from typing import Optional

from pydantic import BaseModel

from backend.constants import (
    MEMORY_TYPE_CHARACTER_GLOBAL,
    MEMORY_TYPE_CHARACTER_KNOWLEDGE,
    MEMORY_TYPE_CHARACTER_PRIVATE,
    MEMORY_TYPE_USER,
)
from backend.services.embedding_service import embedding_service
from backend.services.llm_service import MessageItem
from backend.services.prompt_builder import _generate_time_description
from backend.utils.character_knowledge_validate import (
    build_content,
    build_doc_id,
    validate_key,
)
from backend.utils.dashvector_client import dashvector_client

logger = logging.getLogger(__name__)

# JSON 提取正则：匹配第一个 { ... } 块（支持嵌套）
_JSON_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")


# ============ Step6 结构化输出模型（驼峰命名，与 Step5 snake_case 独立） ============


class Step6ParseError(Exception):
    """Step6 记忆总结 JSON 解析/校验失败异常"""
    pass


class Step6MemoryOutput(BaseModel):
    """
    Step6 记忆总结 LLM 输出的完整结构化模型。

    命名：驼峰（§5.2），与 Step5 snake_case 分属两个独立 LLM 调用的独立 Schema。
    字段清单：R-MEM-07，共 11 字段（含 InnerMonologue 不落库）。
    """
    InnerMonologue: str = ""
    CharacterPublicSettings: str = "无"
    CharacterPrivateSettings: str = "无"
    CharacterKnowledges: str = "无"
    UserSettings: str = "无"
    UserRealName: str = "无"
    UserHobbyName: str = "无"
    UserDescription: str = "无"
    CharacterPurpose: str = "无"
    CharacterAttitude: str = "无"
    RelationDescription: str = "无"


# 11 字段名列表，用于解析时遍历
_ALL_FIELD_NAMES = [
    "InnerMonologue",
    "CharacterPublicSettings",
    "CharacterPrivateSettings",
    "CharacterKnowledges",
    "UserSettings",
    "UserRealName",
    "UserHobbyName",
    "UserDescription",
    "CharacterPurpose",
    "CharacterAttitude",
    "RelationDescription",
]


# ============ JSON 解析 ============


def parse_step6_output(raw_json_str: str) -> Step6MemoryOutput:
    """
    解析 LLM 返回的 Step6 JSON 字符串。

    规则：
    - JSON 不合法 → 抛 Step6ParseError
    - 字段缺失 → 默认「无」（InnerMonologue 默认空字符串）
    - 字段值为非字符串 → 转为 str

    Args:
        raw_json_str: LLM 原始返回文本

    Returns:
        Step6MemoryOutput 实例

    Raises:
        Step6ParseError: JSON 解析失败
    """
    if not raw_json_str or not raw_json_str.strip():
        raise Step6ParseError("Step6 LLM 返回空文本")

    json_str = raw_json_str.strip()

    # 尝试提取 JSON 块
    match = _JSON_PATTERN.search(json_str)
    if match:
        json_str = match.group()

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        raise Step6ParseError(f"Step6 JSON 解析失败: {e}") from e

    if not isinstance(data, dict):
        raise Step6ParseError(f"Step6 JSON 顶层不是对象，类型为 {type(data).__name__}")

    # 对每个字段做缺失兜底
    field_values = {}
    for name in _ALL_FIELD_NAMES:
        raw_val = data.get(name)
        if raw_val is None:
            # InnerMonologue 缺失默认空字符串，其余默认「无」
            field_values[name] = "" if name == "InnerMonologue" else "无"
        elif not isinstance(raw_val, str):
            field_values[name] = str(raw_val)
        else:
            field_values[name] = raw_val

    try:
        return Step6MemoryOutput(**field_values)
    except Exception as e:
        raise Step6ParseError(f"Step6 Pydantic 校验失败: {e}") from e


# ============ Prompt 拼装 ============


# §2.5 完整 few-shot 示例（确认记录 R-MEM-06 / R-MEM-07）
_FEW_SHOT_EXAMPLE = """{
  "InnerMonologue": "他今天又突然问工作压力，其实是在试探我会不会心软妥协。我得先接住情绪，再问一句具体事，别把话题扯到说教上。",
  "CharacterPublicSettings": "外貌-体态-细节：说话时肩膀略绷紧，习惯性地把发丝别到耳后。\\n兴趣-偏好-饮品：最近在学手冲咖啡，但不会主动炫耀技艺。\\n价值观-待人-方式：更愿意先听完再反驳，讨厌被催着表态。",
  "CharacterPrivateSettings": "用户-信任-试探：对方两次用加班当借口爽约，我对「按时出现」的信任在下降，但还不打算当面拆穿。\\n策略-回复-节奏：故意把回复放慢半拍，观察对方会不会补一句解释。",
  "CharacterKnowledges": "咖啡-萃取-时长：知道了闷蒸大约 30 秒能让浅烘豆酸味更柔和。\\n职场-边界-话术：学到一句缓冲话术——「我先听完再帮你拆」。",
  "UserSettings": "作息-惯性-熬夜：经常熬夜到凌晨一两点还在回消息。\\n沟通-偏好-方式：更喜欢被反问一句「你现在最需要什么」而不是直接建议。",
  "UserRealName": "无",
  "UserHobbyName": "阿远",
  "UserDescription": "嘴硬心软型，会用玩笑躲认真话题；对他越是追问越会往后缩，需要留台阶。",
  "CharacterPurpose": "接下来两轮先稳住气氛，不在微信上摊牌约会记录；如果对方再模糊承诺，就用轻松玩笑把皮球踢回去。",
  "CharacterAttitude": "表面平和、内里保留几分试探；愿意陪聊但不急着交底。",
  "RelationDescription": "从「聊得来的网友」过渡到「愿意偶尔互相吐槽工作的熟人」，尚未到暧昧。"
}"""


def build_step6_prompt(
    *,
    persona_text: str,
    level_name: str,
    relation_description: str | None,
    user_real_name: str | None,
    user_hobby_name: str | None,
    user_description: str | None,
    character_purpose: str | None,
    character_attitude: str | None,
    recent_conversations: list,
    step5_messages: list[MessageItem],
    user_input: str,
) -> str:
    """
    拼装 Step6 记忆总结 LLM Prompt。

    模块顺序：系统指令 → 时间 → 人格 → 关系状态 → 近期历史 → 本轮对话 → 任务 → few-shot

    Args:
        persona_text: 人格设定全文（来自 admin_config 或默认）
        level_name: 关系等级名称（如"朋友"）
        relation_description: 关系描述（relationship 表）
        user_real_name: 用户真实称呼
        user_hobby_name: 用户昵称/绰号
        user_description: 用户印象描述
        character_purpose: 角色当前回应策略
        character_attitude: 角色当前态度
        recent_conversations: 最近 N 轮对话（不含本轮，ConversationLog 实例列表）
        step5_messages: 仅 Step5 解析产出的 messages（非 Step5.5 润色后；§2.9.3）
        user_input: 本轮用户输入原文
    """
    # 时间描述
    time_desc = _generate_time_description()

    # 近期历史格式化
    history_lines = []
    for conv in recent_conversations:
        role_label = "用户" if conv.role == "user" else "林小梦"
        history_lines.append(f"{role_label}：{conv.content}")
    history_text = "\n".join(history_lines) if history_lines else "暂无历史对话"

    # 本轮 AI 回复合并（Step5 messages 的 content 拼接）
    ai_reply_parts = [m.content for m in step5_messages if m.content]
    ai_reply_text = "\n".join(ai_reply_parts) if ai_reply_parts else ""

    # 关系状态各字段，None → "无"
    rd = relation_description if relation_description else "暂无"
    urn = user_real_name if user_real_name else "无"
    uhn = user_hobby_name if user_hobby_name else "无"
    ud = user_description if user_description else "无"
    cp = character_purpose if character_purpose else "无"
    ca = character_attitude if character_attitude else "无"

    prompt = (
        "【系统指令】\n"
        "你是林小梦，请对本轮对话进行总结，提取有价值的记忆信息。\n"
        "输出格式要求：仅输出合法 JSON，不含任何前缀、后缀、markdown 标记或注释。\n"
        "所有文本类字段的内容格式为多行 \"key：value\"（中文全角冒号分隔），\n"
        "其中 key 须为三层结构 XXX-XXX-XXX（两段半角连字符连接三段，如「外貌-体态-细节」），\n"
        "无内容时该字段输出字符串\"无\"。\n"
        "\n"
        "【当前时间】\n"
        f"{time_desc}\n"
        "\n"
        "【人格设定】\n"
        f"{persona_text}\n"
        "\n"
        "【关系状态】\n"
        f"当前关系等级：{level_name}\n"
        f"关系描述：{rd}\n"
        f"用户真实称呼：{urn}\n"
        f"用户昵称/绰号：{uhn}\n"
        f"用户印象描述：{ud}\n"
        f"角色当前回应策略：{cp}\n"
        f"角色当前态度倾向：{ca}\n"
        "\n"
        "【近期历史摘要（不含本轮）】\n"
        f"{history_text}\n"
        "\n"
        "【本轮完整对话】\n"
        f"用户：{user_input}\n"
        f"林小梦：{ai_reply_text}\n"
        "\n"
        "【任务】\n"
        "基于以上内容，提取并输出以下 11 个字段的 JSON：\n"
        "\n"
        "1. InnerMonologue：你对本轮对话的内心元思考，不超过150字，不落库。\n"
        "2. CharacterPublicSettings：本次对话中新增或强化的角色公开背景信息。\n"
        "   格式为多行\"key：value\"（全角冒号），每行一条；key 须三层 XXX-XXX-XXX，如\"外貌-体态-细节：说话时肩膀略绷紧\"。\n"
        "   若无新增内容输出\"无\"。\n"
        "3. CharacterPrivateSettings：本次对话中新增的、仅对当前用户可见的角色私有信息。\n"
        "   格式同上。\n"
        "4. CharacterKnowledges：本次对话中体现的角色知识或技能。格式同上。\n"
        "5. UserSettings：本次对话中获取的用户相关信息。格式同上。\n"
        "6. UserRealName：用户的真实称呼。若本轮无法判断或无变化，输出\"无\"。\n"
        "7. UserHobbyName：用户的昵称/绰号。若无变化输出\"无\"。\n"
        "8. UserDescription：对用户的综合印象描述。若无变化输出\"无\"。\n"
        "9. CharacterPurpose：接下来两轮的回应策略规划。\n"
        "10. CharacterAttitude：角色当前对用户的态度倾向。\n"
        "11. RelationDescription：对两人关系的文字描述。若无变化输出\"无\"。\n"
        "\n"
        "合并规则：若某个 key 与上文关系状态中已存在的信息相同 key，\n"
        "请合并新旧 value 后输出一行，不要重复出现相同 key。\n"
        "\n"
        "【输出示例】\n"
        f"{_FEW_SHOT_EXAMPLE}\n"
    )

    return prompt


# ============ STEP-014: key：value 行解析 + 四路向量写入 ============

# Step6 输出字段 → DashVector memory_type 映射
_FIELD_TO_MEMORY_TYPE: dict[str, str] = {
    "CharacterPublicSettings": MEMORY_TYPE_CHARACTER_GLOBAL,
    "CharacterPrivateSettings": MEMORY_TYPE_CHARACTER_PRIVATE,
    "CharacterKnowledges": MEMORY_TYPE_CHARACTER_KNOWLEDGE,
    "UserSettings": MEMORY_TYPE_USER,
}

# 需要携带 user_id 的 memory_type
_TYPES_WITH_USER_ID = {MEMORY_TYPE_CHARACTER_PRIVATE, MEMORY_TYPE_USER}

# 全角冒号
_FULLWIDTH_COLON = "\uff1a"


def parse_kv_lines(text: str) -> list[tuple[str, str]]:
    """
    将多行文本按 \\n 拆行，每行按首处全角冒号分割为 (key, value)。

    规则：
    - 空行跳过
    - 行内无全角冒号 → 丢弃
    - key 或 value 为空白 → 丢弃

    Returns:
        [(key, value), ...] 保留原始顺序
    """
    results: list[tuple[str, str]] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        colon_idx = line.find(_FULLWIDTH_COLON)
        if colon_idx < 0:
            logger.debug("parse_kv_lines: 丢弃无全角冒号的行: %s", line)
            continue
        key = line[:colon_idx].strip()
        value = line[colon_idx + 1:].strip()
        if not key or not value:
            logger.debug("parse_kv_lines: 丢弃 key 或 value 为空的行: %s", line)
            continue
        results.append((key, value))
    return results


async def upsert_step6_vectors(
    output: Step6MemoryOutput,
    user_id: int,
) -> dict[str, int]:
    """
    将 Step6 记忆 LLM 的 4 类记忆字段按行拆分后 upsert 到 DashVector。

    处理流程（每个字段独立）：
    1. 值为「无」→ 整路跳过
    2. 非「无」→ parse_kv_lines 拆行
    3. 每行生成 embedding → upsert（同 key 覆盖由 upsert 语义保证）

    Args:
        output: Step6MemoryOutput 实例
        user_id: 当前用户 ID

    Returns:
        {"character_global": 写入数, "character_private": 写入数, ...}
    """
    write_counts: dict[str, int] = {mt: 0 for mt in _FIELD_TO_MEMORY_TYPE.values()}

    for field_name, memory_type in _FIELD_TO_MEMORY_TYPE.items():
        field_value = getattr(output, field_name, "无")

        # 值为「无」→ 整路跳过
        if field_value.strip() == "无":
            logger.info("Step6 向量写入跳过: field=%s, 值为「无」", field_name)
            continue

        kv_pairs = parse_kv_lines(field_value)
        if not kv_pairs:
            logger.info("Step6 向量写入跳过: field=%s, 无合法 key：value 行", field_name)
            continue

        # 确定是否携带 user_id
        attach_user_id = memory_type in _TYPES_WITH_USER_ID
        effective_user_id = user_id if attach_user_id else None

        for key, value in kv_pairs:
            key_err = validate_key(key)
            if key_err:
                logger.info(
                    "Step6 向量写入跳过: field=%s, key=%s, reason=%s",
                    field_name, key, key_err,
                )
                continue

            doc_id = build_doc_id(memory_type, key, effective_user_id)

            try:
                vector = await embedding_service.get_embedding(value)
                if not vector:
                    logger.warning(
                        "Step6 向量写入: embedding 为空, field=%s, key=%s",
                        field_name, key,
                    )
                    continue
            except Exception as e:
                logger.error(
                    "Step6 向量写入: embedding 失败, field=%s, key=%s, error=%s",
                    field_name, key, str(e),
                )
                continue

            fields: dict = {
                "content": build_content(key, value),
                "stable_key": key,
            }
            if attach_user_id:
                fields["user_id"] = user_id

            success = await dashvector_client.upsert(
                doc_id=doc_id,
                vector=vector,
                fields=fields,
                memory_type=memory_type,
            )
            if success:
                write_counts[memory_type] += 1
                logger.info(
                    "Step6 向量写入成功: doc_id=%s, type=%s", doc_id, memory_type,
                )
            else:
                logger.error(
                    "Step6 向量写入失败: doc_id=%s, type=%s", doc_id, memory_type,
                )

    logger.info("Step6 四路向量写入完成: %s", write_counts)
    return write_counts
