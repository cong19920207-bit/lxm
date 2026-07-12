# -*- coding: utf-8 -*-
# 生活流 Prompt 统一渲染服务（STEP-004）
#
# 职责：
#   1. 按 config_key 从 admin_config 读取 Prompt 模板正文（当前生效版本）。
#   2. 解析 [可选段·xxx]...[/可选段] 条件段（保留/删除）。
#   3. 简单 {{var}} 占位符替换（非 Jinja2）。
#   4. {{lxm_base_persona}} 特殊处理：不从 variables 取，而从现有 IM 系统的
#      active_config:persona 读取，避免同一角色人设两处维护。
#   5. 渲染后残留未替换 {{...}} → 抛 PromptRenderError（防止漏传变量）。

import logging
import re

from backend.services.admin_config_service import admin_config_service

logger = logging.getLogger(__name__)

# 可选段标记：[可选段·条件名] 段内内容 [/可选段]
_OPTIONAL_SEGMENT_PATTERN = re.compile(
    r"\[可选段·(?P<cond>[^\]]+?)\](?P<body>.*?)\[/可选段\]",
    re.DOTALL,
)
# 残留变量检测（双花括号）
_LEFTOVER_VAR_PATTERN = re.compile(r"\{\{\s*[^{}]+?\s*\}\}")

# persona 变量名（复用现有 IM 系统 persona 配置）
_PERSONA_VAR = "lxm_base_persona"
_PERSONA_CONFIG_KEY = "persona"


class PromptRenderError(Exception):
    """Prompt 渲染失败（模板缺失 / 变量遗漏等）"""
    pass


def _apply_optional_segments(text: str, optional_segments: dict[str, bool]) -> str:
    """展开可选段：条件为 True 保留段内内容（去标记），否则整段删除；未提供默认删除。"""
    def _repl(m: re.Match) -> str:
        cond = m.group("cond").strip()
        keep = bool(optional_segments.get(cond, False))
        return m.group("body") if keep else ""

    return _OPTIONAL_SEGMENT_PATTERN.sub(_repl, text)


def _persona_to_text(persona) -> str:
    """persona 配置可能是五字段 dict 或纯字符串；统一转为注入文本。"""
    if persona is None:
        return ""
    if isinstance(persona, dict):
        parts = [str(v).strip() for v in persona.values() if v and str(v).strip()]
        return "\n".join(parts)
    return str(persona)


async def _render_text(
    text: str,
    variables: dict,
    optional_segments: dict[str, bool] | None = None,
) -> str:
    """对给定模板文本执行：可选段展开 → persona 注入 → 变量替换 → 遗漏校验。"""
    optional_segments = optional_segments or {}
    variables = dict(variables or {})

    # 1. 先展开可选段（可能删掉含某些变量的段落，避免误判遗漏）
    text = _apply_optional_segments(text, optional_segments)

    # 2. persona 特殊处理：模板含 {{lxm_base_persona}} 且调用方未显式传入时，从库读取
    if f"{{{{{_PERSONA_VAR}}}}}" in text and _PERSONA_VAR not in variables:
        persona = await admin_config_service.get_active_config(_PERSONA_CONFIG_KEY)
        variables[_PERSONA_VAR] = _persona_to_text(persona)

    # 3. 变量替换
    for key, value in variables.items():
        text = text.replace(f"{{{{{key}}}}}", str(value))

    # 4. 遗漏校验
    leftover = _LEFTOVER_VAR_PATTERN.findall(text)
    if leftover:
        raise PromptRenderError(f"Prompt 存在未替换变量：{leftover}")

    return text


async def render_prompt(
    template_key: str,
    variables: dict | None = None,
    optional_segments: dict[str, bool] | None = None,
) -> str:
    """
    按 config_key 读取模板并渲染。

    Args:
        template_key: admin_config 中的 Prompt config_key（如 prompt_p01_system）
        variables: {{var}} 替换字典
        optional_segments: {条件名: 是否保留}
    Returns:
        渲染后的干净 Prompt 文本
    Raises:
        PromptRenderError: 模板不存在或存在未替换变量
    """
    template = await admin_config_service.get_active_config(template_key)
    if not isinstance(template, str) or not template.strip():
        raise PromptRenderError(f"Prompt 模板不存在或为空：{template_key}")
    return await _render_text(template, variables or {}, optional_segments)
