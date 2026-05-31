# -*- coding: utf-8 -*-
# Step1.5 查询重写 LLM 服务：分析用户意图，生成 3 组检索 QueryQuestion/Keywords
# 需求来源：R-L1L3-09 / R-L1L3-12 / R-L1L3-13 / R-L1L3-14

import json
import logging
import re
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from backend.services.embedding_service import embedding_service
from backend.utils.llm_client import llm_client

logger = logging.getLogger(__name__)

# Step1.5 专用超时：单次 HTTP 上限 45s（传入 llm_client.chat_sync；内层仍最多 3 次 HTTP + 退避）
_STEP1_5_TIMEOUT_SEC = 45.0

# JSON 提取正则：匹配第一个 { ... } 块（支持嵌套）
_JSON_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")


# ============ 输出模型（R-L1L3-09）============


class QueryRewriteOutput(BaseModel):
    """
    Step1.5 LLM 输出的 13 字段结构化模型（C1）。

    相比改造前的 7 字段，新增 CharacterPrivate 独立一组（Question/Keywords/CandidateKeys）
    以及其余三路各自的 CandidateKeys，用于 Step2 的结构化 filter 缩圈。
    四路全为「无」是合法成功态，不再做「至少一组非空」校验。
    """
    InnerMonologue: str = ""

    # 角色公开设定路
    CharacterGlobalQueryQuestion: str = ""
    CharacterGlobalQueryKeywords: str = ""
    CharacterGlobalCandidateKeys: list[str] = Field(default_factory=list)

    # 角色对当前用户的私有设定路（新增独立一组，不再复用 Global）
    CharacterPrivateQueryQuestion: str = ""
    CharacterPrivateQueryKeywords: str = ""
    CharacterPrivateCandidateKeys: list[str] = Field(default_factory=list)

    # 角色知识技能路
    CharacterKnowledgeQueryQuestion: str = ""
    CharacterKnowledgeQueryKeywords: str = ""
    CharacterKnowledgeCandidateKeys: list[str] = Field(default_factory=list)

    # 用户画像与记忆路
    UserProfileQueryQuestion: str = ""
    UserProfileQueryKeywords: str = ""
    UserProfileCandidateKeys: list[str] = Field(default_factory=list)


@dataclass
class QueryRewriteResult:
    """Step1.5 执行结果，供 Step2 消费"""
    success: bool
    output: QueryRewriteOutput | None = None
    # 降级时由 embedding_service 生成的单 Embedding（R-L1L3-12）
    fallback_embedding: list[float] = field(default_factory=list)


# ============ Few-shot 示例（追加到 Step1.5 Prompt 末尾）============

# 覆盖：单条只涉及用户记忆 / 多条连发综合理解 / 私有设定路 / 纯情绪四路全无
_STEP1_5_FEW_SHOT = (
    "【示例（仅供参考输出格式与改写方式，不要照抄内容）】\n"
    "\n"
    "示例1 — 单条，只涉及用户记忆：\n"
    "用户本轮消息：我喜欢吃什么？\n"
    "输出：\n"
    "{\n"
    '  "CharacterGlobalQueryQuestion": "无",\n'
    '  "CharacterGlobalCandidateKeys": [],\n'
    '  "CharacterPrivateQueryQuestion": "无",\n'
    '  "CharacterPrivateCandidateKeys": [],\n'
    '  "CharacterKnowledgeQueryQuestion": "无",\n'
    '  "CharacterKnowledgeCandidateKeys": [],\n'
    '  "UserProfileQueryQuestion": "用户喜欢吃的食物和口味偏好",\n'
    '  "UserProfileCandidateKeys": ["偏好-饮食", "偏好-口味"]\n'
    "}\n"
    "\n"
    "示例2 — 多条连发，综合理解整体意图：\n"
    "用户本轮消息：\n"
    "我对海鲜过敏\n"
    "今晚吃什么好\n"
    "输出：\n"
    "{\n"
    '  "CharacterGlobalQueryQuestion": "无",\n'
    '  "CharacterGlobalCandidateKeys": [],\n'
    '  "CharacterPrivateQueryQuestion": "无",\n'
    '  "CharacterPrivateCandidateKeys": [],\n'
    '  "CharacterKnowledgeQueryQuestion": "无",\n'
    '  "CharacterKnowledgeCandidateKeys": [],\n'
    '  "UserProfileQueryQuestion": "用户的饮食禁忌和今晚的饮食偏好",\n'
    '  "UserProfileCandidateKeys": ["偏好-饮食", "健康-过敏", "习惯-饮食"]\n'
    "}\n"
    "\n"
    "示例3 — 涉及虚拟人私有设定：\n"
    "用户本轮消息：你最近对我印象怎么样？\n"
    "输出：\n"
    "{\n"
    '  "CharacterGlobalQueryQuestion": "无",\n'
    '  "CharacterGlobalCandidateKeys": [],\n'
    '  "CharacterPrivateQueryQuestion": "林小梦对当前用户的印象和态度",\n'
    '  "CharacterPrivateCandidateKeys": ["用户-信任", "关系-态度", "策略-回复"],\n'
    '  "CharacterKnowledgeQueryQuestion": "无",\n'
    '  "CharacterKnowledgeCandidateKeys": [],\n'
    '  "UserProfileQueryQuestion": "无",\n'
    '  "UserProfileCandidateKeys": []\n'
    "}\n"
    "\n"
    "示例4 — 纯情绪，四路全无：\n"
    "用户本轮消息：唉\n"
    "输出：\n"
    "{\n"
    '  "CharacterGlobalQueryQuestion": "无",\n'
    '  "CharacterGlobalCandidateKeys": [],\n'
    '  "CharacterPrivateQueryQuestion": "无",\n'
    '  "CharacterPrivateCandidateKeys": [],\n'
    '  "CharacterKnowledgeQueryQuestion": "无",\n'
    '  "CharacterKnowledgeCandidateKeys": [],\n'
    '  "UserProfileQueryQuestion": "无",\n'
    '  "UserProfileCandidateKeys": []\n'
    "}"
)


# ============ Prompt 拼装 ============


def _build_step1_5_prompt(
    *,
    persona_text: str,
    round_context: dict,
    recent_conversations: list,
    rewrite_input: str,
    source: str = "main",
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

    # 用户消息模块：主链/Step8 文案分支（C17/C19/C20）
    if source == "step8":
        # Step8 输入是 future_action（约 20 字），原标签语义仍准确，保持不变（C17/C20）
        parts.append(f"【用户当前消息】\n{rewrite_input}")
    else:
        # 主链输入是整包 bundled（可能多段），需综合理解整体意图（C19/C20）
        parts.append(
            "【用户本轮消息（可能多段，换行分隔）】\n"
            "请综合理解所有段落的整体意图后改写，"
            "不必逐段单独处理，以整体意图为准。\n"
            f"{rewrite_input}"
        )

    # 任务 + 改写规则 + 输出 Schema（13 字段）
    parts.append(
        "【任务】\n"
        "根据以上内容，为四路记忆检索生成查询语句，输出以下 JSON"
        "（字段名区分大小写，严格遵守）：\n"
        "{\n"
        '  "InnerMonologue": "你对用户消息的内心理解，不超过100字",\n'
        "\n"
        '  "CharacterGlobalQueryQuestion": "用于检索角色公开设定（外貌/性格/兴趣等）的陈述句，不需要时输出\\"无\\"",\n'
        '  "CharacterGlobalQueryKeywords": "关键词1 关键词2 ...",\n'
        '  "CharacterGlobalCandidateKeys": ["外貌-体态", "兴趣-偏好"],\n'
        "\n"
        '  "CharacterPrivateQueryQuestion": "用于检索角色对当前用户的私有态度/策略的陈述句，不需要时输出\\"无\\"",\n'
        '  "CharacterPrivateQueryKeywords": "关键词1 关键词2 ...",\n'
        '  "CharacterPrivateCandidateKeys": ["用户-信任", "策略-回复"],\n'
        "\n"
        '  "CharacterKnowledgeQueryQuestion": "用于检索角色知识技能的陈述句，不需要时输出\\"无\\"",\n'
        '  "CharacterKnowledgeQueryKeywords": "关键词1 关键词2 ...",\n'
        '  "CharacterKnowledgeCandidateKeys": ["咖啡-萃取", "职场-边界"],\n'
        "\n"
        '  "UserProfileQueryQuestion": "用于检索用户画像与记忆的陈述句，不需要时输出\\"无\\"",\n'
        '  "UserProfileQueryKeywords": "关键词1 关键词2 ...",\n'
        '  "UserProfileCandidateKeys": ["经历-出行", "偏好-饮食"]\n'
        "}\n"
        "\n"
        "QueryQuestion 改写规则（四路均适用）：\n"
        "- 禁止保留疑问词（什么、有没有、哪些、怎么、吗、呢）\n"
        "- 禁止以「问」「想知道」「询问」等动词开头\n"
        "- 必须改写为陈述句，语义重心落在「事实内容」上，保留所有关键语义词\n"
        "- 不需要检索该类记忆时，输出空串或字符串「无」\n"
        "\n"
        "CandidateKeys 生成规则（四路均适用）：\n"
        "- 推断用户意图可能命中的记忆分类\n"
        "- 输出二级或三级 Key 前缀，宁多勿少，最多 8 个\n"
        "- Key 格式：XXX-XXX 或 XXX-XXX-XXX\n"
        "- 极度模糊或该路为「无」时，输出空数组 []\n"
        "\n"
        "各路分类参考：\n"
        "- CharacterGlobal（角色公开设定）：外貌-体态 / 兴趣-偏好 / 价值观-待人 / 性格-特征\n"
        "- CharacterPrivate（角色对当前用户私有态度）：用户-信任 / 策略-回复 / 关系-态度\n"
        "- CharacterKnowledge（角色知识技能）：咖啡-萃取 / 职场-边界 / 心理-情绪\n"
        "- UserProfile（用户画像与记忆）：经历-出行 / 偏好-饮食 / 社交-朋友 / 习惯-作息"
    )

    # Few-shot 示例（含多条连发综合理解示例）
    parts.append(_STEP1_5_FEW_SHOT)

    return "\n\n".join(parts)


# ============ JSON 解析 ============


def _parse_query_rewrite_output(raw_text: str) -> QueryRewriteOutput:
    """
    解析 LLM 返回的 Step1.5 JSON 字符串。

    校验口径（C1）：JSON 解析成功 + Pydantic 校验通过即视为成功，
    四路 QueryQuestion 全为「无」/空串是合法成功态，不再抛错。
    仅在「空文本 / JSON 解析失败 / 顶层非对象 / Pydantic 校验失败」时抛 ValueError。
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

    # C1：四路全「无」也算成功，不再做「至少一组非空」校验
    return result


# ============ 核心调用入口 ============


async def execute_query_rewrite(
    *,
    user_id: int,
    rewrite_input: str,
    persona_text: str,
    round_context: dict,
    recent_conversations: list,
    source: str = "main",
) -> QueryRewriteResult:
    """
    执行 Step1.5 查询重写 LLM。

    正常路径：LLM 输出 4 组 QueryQuestion/Keywords/CandidateKeys + InnerMonologue。
    失败路径：整轮「LLM + 解析」仅 1 次，失败后直接降级（不再第二次查询重写）。
    降级路径（R-L1L3-12）：用 rewrite_input 生成单 Embedding 作为统一 fallback。

    Args:
        user_id: 用户 ID
        rewrite_input: 改写输入文本（C25）。主链为 bundled_truncated（整包截断），
            Step8 为 future_action（约 20 字）；降级时用于生成 fallback Embedding
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
        rewrite_input=rewrite_input,
        source=source,
    )

    last_error: str = ""

    start_time = time.monotonic()
    try:
        raw_text = await llm_client.chat_sync(
            prompt, timeout_sec=_STEP1_5_TIMEOUT_SEC
        )
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        output = _parse_query_rewrite_output(raw_text)

        logger.info(
            "Step1.5 查询重写成功: user_id=%d elapsed=%dms source=%s",
            user_id, elapsed_ms, source,
        )
        return QueryRewriteResult(success=True, output=output)

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        last_error = str(e)
        logger.warning(
            "Step1.5 查询重写失败: user_id=%d elapsed=%dms error=%s source=%s",
            user_id, elapsed_ms, last_error, source,
        )

    # 本轮失败后直接降级（R-L1L3-12）
    logger.error(
        "Step1.5 查询重写最终失败，启动降级: user_id=%d "
        "last_error=%s source=%s",
        user_id, last_error, source,
    )

    return await _fallback_with_embedding(
        user_id=user_id,
        text=rewrite_input,
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
