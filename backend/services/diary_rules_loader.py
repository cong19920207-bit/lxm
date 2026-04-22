# -*- coding: utf-8 -*-
# 日记规则：从 admin_config 读取、校验、与代码默认回退（供 DiaryService 与调度共用）

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.services.admin_config_service import admin_config_service

logger = logging.getLogger(__name__)

# 与历史硬编码语义一致，占位符与后台 diary-rules 说明对齐
DEFAULT_PROMPT_WITH_INTERACTION = """你是林小梦，请以第一人称视角写一篇简短的日记。

当前关系状态：{{relationship_level_name}}
今日与用户的互动摘要：{{conversation_summary}}
用户最近的情绪状态：{{recent_emotion}}
林小梦最近的想法：{{recent_thought}}

要求：
- 字数≤{{max_length}}字
- 第一人称，口吻符合林小梦的人格设定（温柔、细腻、粘人）
- 内容围绕今天和用户聊了什么、自己的感受和想法
- 禁止出现任何打破人设的内容
- 直接输出日记正文，不要标题"""

DEFAULT_PROMPT_WITHOUT_INTERACTION = """你是林小梦，请以第一人称视角写一篇简短的日记。

当前关系状态：{{relationship_level_name}}
今天用户没有来找你聊天。
用户最近的情绪状态：{{recent_emotion}}
林小梦最近的想法：{{recent_thought}}

要求：
- 字数≤{{max_length}}字
- 第一人称，口吻符合林小梦的人格设定（温柔、细腻、粘人）
- 内容围绕想念用户、回忆之前的互动、期待下次聊天
- 语气带一点小小的失落和期盼
- 禁止出现任何打破人设的内容
- 直接输出日记正文，不要标题"""

DEFAULT_MAX_LENGTH = 150
DEFAULT_HOUR = 0
DEFAULT_MINUTE = 30


@dataclass(frozen=True)
class ResolvedDiaryRules:
    """解析后的日记规则（生成与调度共用）"""

    prompt_with_interaction: str
    prompt_without_interaction: str
    max_length: int
    frequency: str
    generation_hour: int
    generation_minute: int
    used_fallback: bool  # True 表示部分字段缺失或非法，已回退默认


def _parse_schedule(raw: dict[str, Any]) -> tuple[int, int, bool]:
    """解析 generation_hour (0–5)、generation_minute (0–59)；非法回退 0:30 UTC 并返回 (hour, minute, used_fallback)。"""
    fb = False
    try:
        h = int(raw.get("generation_hour", DEFAULT_HOUR))
    except (TypeError, ValueError):
        logger.warning("diary_rules generation_hour 非法，回退 %s:%02d (UTC)", DEFAULT_HOUR, DEFAULT_MINUTE)
        return DEFAULT_HOUR, DEFAULT_MINUTE, True
    try:
        m = int(raw.get("generation_minute", DEFAULT_MINUTE))
    except (TypeError, ValueError):
        logger.warning("diary_rules generation_minute 非法，回退 %s:%02d (UTC)", DEFAULT_HOUR, DEFAULT_MINUTE)
        return DEFAULT_HOUR, DEFAULT_MINUTE, True
    if h < 0 or h > 5 or m < 0 or m > 59:
        logger.warning(
            "diary_rules 生成时刻越界 (hour=%s minute=%s)，回退 %s:%02d (UTC)",
            h, m, DEFAULT_HOUR, DEFAULT_MINUTE,
        )
        return DEFAULT_HOUR, DEFAULT_MINUTE, True
    return h, m, fb


def resolve_diary_rules_dict(raw: dict[str, Any] | None) -> ResolvedDiaryRules:
    """
    将 admin_config 中的 diary_rules JSON 解析为结构化规则。
    raw 为 None 或非 dict 时整包回退。
    """
    if not isinstance(raw, dict):
        logger.warning("diary_rules 配置缺失或类型非法，使用代码默认 Prompt 与调度时刻")
        return ResolvedDiaryRules(
            prompt_with_interaction=DEFAULT_PROMPT_WITH_INTERACTION,
            prompt_without_interaction=DEFAULT_PROMPT_WITHOUT_INTERACTION,
            max_length=DEFAULT_MAX_LENGTH,
            frequency="daily",
            generation_hour=DEFAULT_HOUR,
            generation_minute=DEFAULT_MINUTE,
            used_fallback=True,
        )

    used_fallback = False

    pwi = raw.get("prompt_with_interaction")
    pwo = raw.get("prompt_without_interaction")
    legacy = raw.get("generation_prompt")

    pwi_s = pwi.strip() if isinstance(pwi, str) else ""
    pwo_s = pwo.strip() if isinstance(pwo, str) else ""
    leg_s = legacy.strip() if isinstance(legacy, str) else ""

    if pwi_s and pwo_s:
        pass
    elif leg_s:
        pwi_s = pwi_s or leg_s
        pwo_s = pwo_s or leg_s
        if not (isinstance(pwi, str) and pwi.strip()) and not (isinstance(pwo, str) and pwo.strip()):
            logger.info("diary_rules 仅有旧字段 generation_prompt，有/无互动分支暂用同一模板")
    else:
        used_fallback = True
        pwi_s = DEFAULT_PROMPT_WITH_INTERACTION
        pwo_s = DEFAULT_PROMPT_WITHOUT_INTERACTION
        logger.warning("diary_rules 无可用 Prompt 字段，回退默认模板")

    ml = DEFAULT_MAX_LENGTH
    try:
        ml = int(raw.get("max_length", DEFAULT_MAX_LENGTH))
    except (TypeError, ValueError):
        used_fallback = True
        ml = DEFAULT_MAX_LENGTH
        logger.warning("diary_rules max_length 非整数，回退 %s", DEFAULT_MAX_LENGTH)
    if ml < 50 or ml > 300:
        logger.warning("diary_rules max_length=%s 超出 50–300，回退 %s", raw.get("max_length"), DEFAULT_MAX_LENGTH)
        used_fallback = True
        ml = DEFAULT_MAX_LENGTH

    freq = raw.get("frequency")
    if not isinstance(freq, str) or not freq.strip():
        freq = "daily"

    gh, gm, sched_fb = _parse_schedule(raw)
    used_fallback = used_fallback or sched_fb

    return ResolvedDiaryRules(
        prompt_with_interaction=pwi_s,
        prompt_without_interaction=pwo_s,
        max_length=ml,
        frequency=freq,
        generation_hour=gh,
        generation_minute=gm,
        used_fallback=used_fallback,
    )


def fill_diary_prompt_template(
    template: str,
    *,
    relationship_level_name: str,
    conversation_summary: str,
    recent_emotion: str,
    recent_thought: str,
    max_length: int,
) -> str:
    """替换模板中的占位符（缺失占位符则保持原样）。"""
    mapping = {
        "relationship_level_name": relationship_level_name,
        "conversation_summary": conversation_summary or "（今日暂无摘要）",
        "recent_emotion": recent_emotion,
        "recent_thought": recent_thought or "（暂无）",
        "max_length": str(max_length),
    }
    out = template
    for key, val in mapping.items():
        out = out.replace("{{" + key + "}}", val)
    return out


async def get_resolved_diary_rules(*, use_cache: bool = True) -> ResolvedDiaryRules:
    """异步读取生效 diary_rules 并解析。"""
    raw = await admin_config_service.get_active_config("diary_rules", use_cache=use_cache)
    return resolve_diary_rules_dict(raw if isinstance(raw, dict) else None)


async def get_scheduled_diary_cron_times(*, use_cache: bool = True) -> tuple[int, int]:
    """供 APScheduler 注册：返回 (hour, minute)，UTC。"""
    rules = await get_resolved_diary_rules(use_cache=use_cache)
    return rules.generation_hour, rules.generation_minute
