# -*- coding: utf-8 -*-
# 对话流 Prompt 只读展示：从运行时同源常量/拼装函数生成后台预览数据（不做配置）

from __future__ import annotations

from backend.services.prompt_builder import (
    ACTIVE_TRIGGER_INSTRUCTIONS,
    AGENT_TASK_OUTPUT_SUFFIX,
    EMOTION_MAPPING,
    EMPATHY_RULES,
    LEVEL_DEFINITIONS,
    MODULE_ORDER,
    MODULE_TOKEN_LIMITS,
    SILENCE_CORRECTION_8_14,
    SILENCE_CORRECTION_15_PLUS,
    STEP8_PROACTIVE_INPUT_TEMPLATE,
    TRIM_PRIORITY,
)
from backend.services.query_rewrite_service import _build_step1_5_prompt

# 模块中文说明（仅展示用）
_MODULE_LABELS = {
    "system": "System（可配置：Prompt · Step5）",
    "persona": "Persona（可配置：人格管理）",
    "character_knowledge": "角色设定与知识（Step2 检索注入）",
    "relationship": "关系状态（含等级语气 / 沉默修正）",
    "memory": "用户记忆（Step2 user 路注入）",
    "emotion": "情绪状态（含共情规则）",
    "time_activity": "时间与活动状态",
    "recent_chat": "最近对话",
    "user_nickname": "用户称呼",
    "user_input": "用户消息（Step8 替换为【主动发起】）",
}


def _placeholder_round_context() -> dict:
    return {
        "time_description": "{{time_description}}",
        "activity_description": "{{activity_description}}",
        "level_name": "{{level_name}}",
        "relation_description": "{{relation_description}}",
        "user_real_name": "{{user_real_name}}",
        "user_hobby_name": "{{user_hobby_name}}",
    }


def get_step15_prompt_view() -> dict:
    """Step1.5 查询重写：模板 + 占位符拼装预览（主链 / Step8 分支）。"""
    round_ctx = _placeholder_round_context()
    recent = [{"role": "user", "content": "{{recent_chat_line}}"}]
    main_tpl = _build_step1_5_prompt(
        persona_text="{{persona}}",
        round_context=round_ctx,
        recent_conversations=recent,
        rewrite_input="{{rewrite_input}}",
        source="main",
    )
    step8_tpl = _build_step1_5_prompt(
        persona_text="{{persona}}",
        round_context=round_ctx,
        recent_conversations=recent,
        rewrite_input="{{future_action}}",
        source="step8",
    )
    return {
        "readonly": True,
        "title": "Step1.5 查询重写",
        "description": (
            "对话前为四路记忆检索生成 Query。下方为与运行时同源的拼装模板；"
            "{{…}} 为运行时注入，非固定文案。"
        ),
        "source_file": "backend/services/query_rewrite_service.py",
        "variants": [
            {
                "key": "main",
                "label": "主链（source=main）",
                "content": main_tpl,
            },
            {
                "key": "step8",
                "label": "Step8 子链（source=step8）",
                "content": step8_tpl,
            },
        ],
    }


def get_step3_prompt_view() -> dict:
    """Step3 Prompt 拼装：模块顺序 + 硬编码语气/共情/沉默（只读）。"""
    modules = []
    for key in MODULE_ORDER:
        modules.append({
            "key": key,
            "label": _MODULE_LABELS.get(key, key),
            "token_limit_default": MODULE_TOKEN_LIMITS.get(key),
        })
    level_items = []
    for level, meta in sorted(LEVEL_DEFINITIONS.items()):
        level_items.append({
            "level": level,
            "name": meta["name"],
            "behavior": meta["behavior"],
        })
    # EMOTION_MAPPING 中 None 表示保持当前 AI 情绪
    emotion_map = {
        k: (v if v is not None else "保持当前AI情绪")
        for k, v in EMOTION_MAPPING.items()
    }
    return {
        "readonly": True,
        "title": "Step3 Prompt 拼装",
        "description": (
            "将各模块拼成喂给 Step5 的完整 Prompt。"
            "System / Persona 可在对应后台页配置；本页展示硬编码拼装规则与注入文案。"
        ),
        "source_file": "backend/services/prompt_builder.py",
        "module_order": modules,
        "trim_priority": list(TRIM_PRIORITY),
        "empathy_rules": dict(EMPATHY_RULES),
        "emotion_mapping": emotion_map,
        "level_definitions": level_items,
        "silence_corrections": [
            {
                "range": "8～14 天",
                "text": SILENCE_CORRECTION_8_14,
            },
            {
                "range": "≥15 天",
                "text": SILENCE_CORRECTION_15_PLUS,
            },
        ],
    }


def get_step8_prompt_view() -> dict:
    """Step8 Future：【主动发起】模块模板（其余复用主链）。"""
    return {
        "readonly": True,
        "title": "Step8 Future 主动",
        "description": (
            "Future 槽到期触发。除模块9【主动发起】外，复用 Step1.5 / Step2 / Step3 / Step5 / Step5.5。"
            "{{future_action}} 为槽内意图摘要。"
        ),
        "source_file": "backend/services/prompt_builder.py",
        "proactive_input_template": STEP8_PROACTIVE_INPUT_TEMPLATE,
        "notes": [
            "trigger_type 落库为 FUTURE",
            "与 Agent P0～P4（规则触发）是不同链路",
        ],
    }


def get_agent_prompt_view() -> dict:
    """Agent P0～P4：主动任务指令（独立于 Step8）。"""
    triggers = []
    for key in ("P0", "P1", "P2", "P3", "P4"):
        task = ACTIVE_TRIGGER_INSTRUCTIONS.get(key, "")
        triggers.append({
            "key": key,
            "task_instruction": task,
            "full_task_block": task + AGENT_TASK_OUTPUT_SUFFIX,
        })
    return {
        "readonly": True,
        "title": "Agent 主动（P0～P4）",
        "description": (
            "定时规则触发的主动消息任务指令。System / Persona 复用主链配置；"
            "本页仅展示各触发类型的任务段（硬编码，只读）。"
        ),
        "source_file": "backend/services/prompt_builder.py",
        "output_suffix": AGENT_TASK_OUTPUT_SUFFIX.strip(),
        "triggers": triggers,
    }
