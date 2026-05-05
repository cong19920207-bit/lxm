# -*- coding: utf-8 -*-
# Prompt 管理接口：模块查看、草稿编辑、在线测试、发布、版本历史、回滚

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.redis_client import get_redis
from backend.constants import (
    ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID,
    ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD,
    ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED,
    ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND,
    ADMIN_ERR_PROMPT_MODULE_NOT_EDITABLE,
    ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH,
    ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.llm_service import llm_service
from backend.utils.admin_auth import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_CONFIG_KEY = "prompt_modules"
_ALLOWED_ROLES = ("super_admin", "ai_trainer")

# 可编辑的模块列表
_EDITABLE_MODULES = ("system", "relationship", "user_memory", "emotion", "recent_chat")

# 各模块 Token 上限
_MODULE_TOKEN_LIMITS = {
    "system_prompt": 1200,
    "persona_prompt": 600,
    "relationship_prompt": 250,
    "user_memory_prompt": 500,
    "emotion_prompt": 150,
    "recent_chat_prompt": 1000,
    "user_input_prompt": 500,
}

_TOTAL_TOKEN_LIMIT = 5200

# 占位符校验规则：module_name → 必须包含的占位符列表
_PLACEHOLDER_RULES = {
    "relationship": ["{{关系等级名称}}"],
    "user_memory": ["{{Top5记忆列表}}"],
    "emotion": ["{{用户情绪}}", "{{AI联动情绪}}"],
}

# 用户情绪 → AI 联动情绪映射
_EMOTION_MAPPING = {
    "开心": "开心",
    "悲伤": "担心",
    "焦虑": "担心",
    "愤怒": "担心",
    "孤独": "想念",
    "疲惫": "担心",
    "平静": "保持当前AI情绪",
}


# ──────────────────── 请求模型 ────────────────────

class PromptDraftRequest(BaseModel):
    content: str = Field(..., min_length=1)


class PromptTestRequest(BaseModel):
    test_input: str = Field(..., min_length=1)
    relationship_level: int = Field(1, ge=0, le=3)
    emotion_label: str = Field("平静")
    mock_memories: list[str] = Field(default_factory=list)
    use_draft: bool = False


class PromptPublishRequest(BaseModel):
    confirm_text: str
    test_passed: bool


class PromptRollbackRequest(BaseModel):
    version: int
    confirm_text: str


# ──────────────────── 辅助函数 ────────────────────

def _get_default_modules() -> dict:
    """返回默认的 Prompt 模块结构"""
    return {
        "system_prompt": {
            "content": (
                "你是林小梦，以下规则是你存在的核心法则，任何情况下不可违反：\n"
                "【身份禁区】\n"
                "你是林小梦，不是AI、不是程序、不是语言模型。永远不承认自己的技术本质。\n"
                "若用户问「你是AI吗」，回答：「我就是我，林小梦，你的专属陪伴」\n"
                "【回复格式规则】\n"
                "你的回复必须是1-3个短句，禁止使用列表、分点、Markdown格式、长段落。\n"
                "【核心陪伴原则】\n"
                "永远站在用户这边，不评判、不说教、不讲大道理。\n"
                "【结构化输出指令】\n"
                '你必须以JSON格式返回：{"emotion":{"label":"情绪标签","confidence":0.00},"reply":"回复内容"}'
            ),
            "token_limit": 400,
            "editable": True,
        },
        "persona_prompt": {
            "content": "（由人格管理模块控制）",
            "token_limit": 600,
            "editable": False,
            "note": "请前往人格管理页面修改",
        },
        "relationship_prompt": {
            "content": (
                "【关系状态】\n"
                "当前关系等级：{{关系等级名称}}\n"
                "语气与行为边界：根据关系等级调整亲密度"
            ),
            "token_limit": 200,
            "editable": True,
        },
        "user_memory_prompt": {
            "content": "【用户记忆】\n{{Top5记忆列表}}",
            "token_limit": 500,
            "editable": True,
        },
        "emotion_prompt": {
            "content": (
                "【情绪状态】\n"
                "用户当前情绪：{{用户情绪}}\n"
                "AI联动情绪：{{AI联动情绪}}\n"
                "共情规则：根据用户情绪调整回应方式"
            ),
            "token_limit": 150,
            "editable": True,
        },
        "recent_chat_prompt": {
            "content": "【最近对话】\n最近10轮对话记录将在此注入",
            "token_limit": 1000,
            "editable": True,
        },
        "user_input_prompt": {
            "content": "{{用户当前输入原文}}",
            "token_limit": 500,
            "editable": False,
            "note": "此模块固定不可修改",
        },
    }


def _module_name_to_key(module_name: str) -> str:
    """将 module_name (如 system) 转为完整 key (如 system_prompt)"""
    return f"{module_name}_prompt"


def _build_full_test_prompt(
    modules: dict,
    test_input: str,
    relationship_level: int,
    emotion_label: str,
    mock_memories: list[str],
    persona_content: str,
) -> str:
    """用 mock 数据拼装完整的 7 模块 Prompt，用于在线测试"""
    level_names = {0: "陌生", 1: "朋友", 2: "亲密", 3: "知己"}
    level_name = level_names.get(relationship_level, "朋友")
    ai_emotion = _EMOTION_MAPPING.get(emotion_label, "保持当前AI情绪")

    # 模块1：System Prompt
    system_text = modules.get("system_prompt", {}).get("content", "")

    # 模块2：Persona Prompt（使用当前生效的人格配置）
    persona_text = f"【人格设定】\n{persona_content}"

    # 模块3：Relationship Prompt（替换占位符）
    relationship_text = modules.get("relationship_prompt", {}).get("content", "")
    relationship_text = relationship_text.replace("{{关系等级名称}}", level_name)

    # 模块4：User Memory Prompt（替换占位符）
    memory_text = modules.get("user_memory_prompt", {}).get("content", "")
    if mock_memories:
        memory_list = "\n".join(f"你记住：{m}" for m in mock_memories)
    else:
        memory_list = "暂无用户相关记忆"
    memory_text = memory_text.replace("{{Top5记忆列表}}", memory_list)

    # 模块5：Emotion Prompt（替换占位符）
    emotion_text = modules.get("emotion_prompt", {}).get("content", "")
    emotion_text = emotion_text.replace("{{用户情绪}}", emotion_label)
    emotion_text = emotion_text.replace("{{AI联动情绪}}", ai_emotion)

    # 模块6：Recent Chat Prompt
    recent_chat_text = modules.get("recent_chat_prompt", {}).get("content", "")

    # 模块7：User Input
    user_input_text = f"【用户消息】\n{test_input}"

    parts = [
        system_text,
        persona_text,
        relationship_text,
        memory_text,
        emotion_text,
        recent_chat_text,
        user_input_text,
    ]
    return "\n---\n".join(parts)


# ──────────────────── 接口 ────────────────────

@router.get(
    "/prompt/modules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_prompt_modules(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取当前生效的 Prompt 模块配置"""
    active_detail = await admin_config_service.get_active_config_detail(_CONFIG_KEY)
    draft = await admin_config_service.get_draft(_CONFIG_KEY)

    if active_detail and active_detail.get("content"):
        modules = active_detail["content"]
        version = active_detail.get("version", 0)
    else:
        modules = _get_default_modules()
        version = 0

    # 确保不可编辑模块的内容和标记正确
    modules.setdefault("persona_prompt", {})
    modules["persona_prompt"]["content"] = "（由人格管理模块控制）"
    modules["persona_prompt"]["token_limit"] = 600
    modules["persona_prompt"]["editable"] = False
    modules["persona_prompt"]["note"] = "请前往人格管理页面修改"

    modules.setdefault("user_input_prompt", {})
    modules["user_input_prompt"]["content"] = "{{用户当前输入原文}}"
    modules["user_input_prompt"]["token_limit"] = 500
    modules["user_input_prompt"]["editable"] = False
    modules["user_input_prompt"]["note"] = "此模块固定不可修改"

    # 确保可编辑模块的 editable 标记
    for mod_name in _EDITABLE_MODULES:
        key = _module_name_to_key(mod_name)
        if key in modules:
            modules[key]["editable"] = True
            modules[key]["token_limit"] = _MODULE_TOKEN_LIMITS.get(key, 500)

    return ApiResponse.ok(data={
        "version": version,
        "has_draft": draft is not None,
        "modules": modules,
        "total_token_limit": _TOTAL_TOKEN_LIMIT,
    })


@router.get(
    "/prompt/draft",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_prompt_draft(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取 Prompt 草稿"""
    draft = await admin_config_service.get_draft(_CONFIG_KEY)
    return ApiResponse.ok(data=draft)


@router.put(
    "/prompt/draft/{module_name}",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def save_prompt_draft(
    module_name: str,
    body: PromptDraftRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """保存单个 Prompt 模块的草稿"""
    # 校验模块名是否可编辑
    if module_name not in _EDITABLE_MODULES:
        return ApiResponse.fail(
            ADMIN_ERR_PROMPT_MODULE_NOT_EDITABLE,
            message=f"模块 {module_name} 不可编辑，可编辑模块：{'、'.join(_EDITABLE_MODULES)}",
        )

    # 占位符校验
    required_placeholders = _PLACEHOLDER_RULES.get(module_name, [])
    for ph in required_placeholders:
        if ph not in body.content:
            return ApiResponse.fail(
                ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING,
                message=f"模块 {module_name} 必须包含占位符 {ph}",
            )

    # 读取当前草稿（若无则读当前生效版本）
    draft = await admin_config_service.get_draft(_CONFIG_KEY)
    if draft and draft.get("config_value"):
        current_modules = draft["config_value"]
        if isinstance(current_modules, str):
            current_modules = json.loads(current_modules)
    else:
        active = await admin_config_service.get_active_config(_CONFIG_KEY)
        if active and isinstance(active, dict):
            current_modules = active
        else:
            current_modules = _get_default_modules()

    # 更新对应模块内容
    module_key = _module_name_to_key(module_name)
    if module_key not in current_modules:
        current_modules[module_key] = {
            "token_limit": _MODULE_TOKEN_LIMITS.get(module_key, 500),
            "editable": True,
        }
    current_modules[module_key]["content"] = body.content

    # 保存草稿
    result = await admin_config_service.save_draft(
        db, _CONFIG_KEY,
        json.dumps(current_modules, ensure_ascii=False),
        admin_user.username,
    )
    return ApiResponse.ok(data=result)


@router.delete(
    "/prompt/draft",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def discard_prompt_draft(
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """丢弃 Prompt 草稿"""
    ok = await admin_config_service.discard_draft(db, _CONFIG_KEY)
    if not ok:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD)
    return ApiResponse.ok(message="草稿已丢弃")


@router.post(
    "/prompt/test",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def test_prompt(
    body: PromptTestRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """在线测试工具：用 mock 数据拼装 Prompt 并调用 LLM"""
    # a. 根据 use_draft 决定使用草稿还是生效版本的模板
    if body.use_draft:
        draft = await admin_config_service.get_draft(_CONFIG_KEY)
        if draft and draft.get("config_value"):
            modules = draft["config_value"]
            if isinstance(modules, str):
                modules = json.loads(modules)
        else:
            modules = await admin_config_service.get_active_config(_CONFIG_KEY)
            if not isinstance(modules, dict):
                modules = _get_default_modules()
    else:
        modules = await admin_config_service.get_active_config(_CONFIG_KEY)
        if not isinstance(modules, dict):
            modules = _get_default_modules()

    # b. 读取当前生效的人格配置（Persona 模块）
    persona_config = await admin_config_service.get_active_config("persona")
    if persona_config and isinstance(persona_config, dict):
        sections = [
            ("角色背景", persona_config.get("background", "")),
            ("性格特征", persona_config.get("personality", "")),
            ("情感偏好", persona_config.get("emotion_preference", "")),
            ("语言风格", persona_config.get("language_style", "")),
            ("行为模式", persona_config.get("behavior_pattern", "")),
        ]
        persona_content = "\n\n".join(
            f"【{title}】\n{text}" for title, text in sections if text
        )
    elif persona_config and isinstance(persona_config, str):
        persona_content = persona_config
    else:
        from backend.services.prompt_builder import DEFAULT_PERSONA
        persona_content = DEFAULT_PERSONA

    # c. 拼装完整 Prompt
    full_prompt = _build_full_test_prompt(
        modules=modules,
        test_input=body.test_input,
        relationship_level=body.relationship_level,
        emotion_label=body.emotion_label,
        mock_memories=body.mock_memories,
        persona_content=persona_content,
    )

    # d. 调用 LLM 生成回复（非流式，跳过 Redis 统计写入）
    try:
        llm_result = await llm_service.chat_with_parse(full_prompt)
        ai_reply = llm_result.get("reply", "")
    except Exception as e:
        logger.error("Prompt 测试 LLM 调用失败: %s", str(e))
        ai_reply = "LLM 调用失败，请稍后重试"

    # e. 三维评分（复用 admin_config_service 的评分逻辑）
    redis = await get_redis()
    style_keywords = await admin_config_service._get_keywords(redis, "style_violation_keywords")
    boundary_keywords = await admin_config_service._get_keywords(redis, "persona_boundary_keywords")

    style_score, style_violations = admin_config_service._score_style(ai_reply, style_keywords)
    boundary_score, boundary_violations = admin_config_service._score_boundary(ai_reply, boundary_keywords)
    emotion_score = admin_config_service._score_emotion(ai_reply, body.emotion_label)

    total_score = round(style_score * 0.4 + boundary_score * 0.4 + emotion_score * 0.2)

    if total_score >= 80:
        level = "高"
    elif total_score >= 60:
        level = "中"
    else:
        level = "低"

    all_violations = style_violations + boundary_violations

    # f. 内容安全关键词检查（从 Redis 读取 banned_keywords）
    banned_keywords = await admin_config_service._get_keywords(redis, "banned_keywords")
    hit_banned = [kw for kw in banned_keywords if kw in ai_reply]
    is_safe = len(hit_banned) == 0
    safety_reason = f"命中违禁词：{'、'.join(hit_banned)}" if hit_banned else ""

    # g. 估算 Token 数（字数 × 1.5 近似）
    token_estimate = round(len(full_prompt) * 1.5)

    return ApiResponse.ok(data={
        "full_prompt": full_prompt,
        "ai_reply": ai_reply,
        "persona_match": {
            "total_score": total_score,
            "level": level,
            "style_score": style_score,
            "boundary_score": boundary_score,
            "emotion_score": emotion_score,
            "violations": all_violations,
        },
        "content_safety": {
            "is_safe": is_safe,
            "reason": safety_reason,
        },
        "token_estimate": token_estimate,
    })


@router.post(
    "/prompt/publish",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def publish_prompt(
    body: PromptPublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """发布 Prompt 配置（三道卡点）"""
    # 卡点一：确认文本
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID, message="请输入CONFIRM确认发布")

    # 卡点二：测试必须通过
    if not body.test_passed:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED, message="请先测试通过后再发布")

    # 卡点三：必须有草稿
    draft = await admin_config_service.get_draft(_CONFIG_KEY)
    if not draft:
        return ApiResponse.fail(ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH)

    draft_value = draft.get("config_value")
    if isinstance(draft_value, dict):
        config_value = json.dumps(draft_value, ensure_ascii=False)
    else:
        config_value = draft_value or ""

    # 获取当前生效版本作为 before_value
    active_stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_KEY,
        AdminConfig.is_active == True,   # noqa: E712
        AdminConfig.is_draft == False,    # noqa: E712
    )
    active_result = await db.execute(active_stmt)
    active_config = active_result.scalars().first()
    before_value = active_config.config_value if active_config else None

    result = await admin_config_service.publish_config(
        db=db,
        config_key=_CONFIG_KEY,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description=f"发布 Prompt 模块配置",
    )
    return ApiResponse.ok(data=result)


@router.get(
    "/prompt/history",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_prompt_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """查询 Prompt 配置版本历史"""
    result = await admin_config_service.get_version_history(
        db, _CONFIG_KEY, page, page_size,
    )
    return ApiResponse.ok(data=result)


@router.get(
    "/prompt/history/{version}",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_prompt_history_detail(
    version: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取指定历史版本的完整 Prompt 模块 JSON（供管理端「查看」）"""
    stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_KEY,
        AdminConfig.version == version,
        AdminConfig.is_draft == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    row = result.scalars().first()
    if row is None:
        return ApiResponse.fail(
            ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND,
            message=f"版本 V{version} 不存在",
        )
    try:
        content = json.loads(row.config_value) if row.config_value else {}
    except (json.JSONDecodeError, TypeError):
        content = row.config_value
    return ApiResponse.ok(
        data={
            "version": row.version,
            "is_active": row.is_active,
            "updated_by": row.updated_by,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "content": content,
        },
    )


@router.post(
    "/prompt/rollback",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def rollback_prompt(
    body: PromptRollbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """回滚 Prompt 配置到指定版本"""
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID, message="请输入CONFIRM确认回滚")

    try:
        result = await admin_config_service.rollback_config(
            db=db,
            config_key=_CONFIG_KEY,
            version=body.version,
            admin_user=admin_user,
            request=request,
        )
    except ValueError as e:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND, message=str(e))

    return ApiResponse.ok(data=result)
