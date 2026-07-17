# -*- coding: utf-8 -*-
# 人格管理接口：草稿、测试、发布、版本历史、回滚

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
from backend.constants import (
    ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID,
    ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD,
    ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED,
    ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND,
    ADMIN_ERR_PERSONA_FIELD_EMPTY,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.utils.admin_auth import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_CONFIG_KEY = "persona"
_READ_ROLES = ("super_admin", "ai_trainer", "observer")
_WRITE_ROLES = ("super_admin", "ai_trainer")

_PERSONA_FIELDS = ("background", "personality", "emotion_preference",
                    "language_style", "behavior_pattern")


# ──────────────────── 请求模型 ────────────────────

class PersonaContent(BaseModel):
    background: str = Field(..., min_length=1)
    personality: str = Field(..., min_length=1)
    emotion_preference: str = Field(..., min_length=1)
    language_style: str = Field(..., min_length=1)
    behavior_pattern: str = Field(..., min_length=1)


class PersonaDraftRequest(BaseModel):
    content: PersonaContent


class PersonaTestRequest(BaseModel):
    draft_content: PersonaContent


class PersonaPublishRequest(BaseModel):
    content: PersonaContent
    test_passed: bool
    confirm_text: str


class PersonaRollbackRequest(BaseModel):
    version: int
    confirm_text: str


# ──────────────────── 辅助函数 ────────────────────

def _validate_persona_content(content: dict) -> str | None:
    """校验人格 5 个字段均不为空，返回错误信息或 None"""
    for field in _PERSONA_FIELDS:
        val = content.get(field)
        if not val or not str(val).strip():
            return f"字段 {field} 不可为空"
    return None


def _format_persona_prompt(content: dict) -> str:
    """将人格 5 区域内容格式化为 Prompt 字符串"""
    sections = [
        ("角色背景", content.get("background", "")),
        ("性格特征", content.get("personality", "")),
        ("情感偏好", content.get("emotion_preference", "")),
        ("语言风格", content.get("language_style", "")),
        ("行为模式", content.get("behavior_pattern", "")),
    ]
    return "\n\n".join(f"【{title}】\n{text}" for title, text in sections if text)


# ──────────────────── 接口 ────────────────────

@router.get(
    "/persona/current",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_persona_current(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取当前生效人格配置 + 草稿状态"""
    detail = await admin_config_service.get_active_config_detail(_CONFIG_KEY)
    draft = await admin_config_service.get_draft(_CONFIG_KEY)

    if detail is None and draft is None:
        return ApiResponse.ok(data=None)

    data = detail or {
        "version": 0,
        "updated_by": None,
        "updated_at": None,
        "content": None,
    }
    data["has_draft"] = draft is not None

    return ApiResponse.ok(data=data)


@router.get(
    "/persona/draft",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_persona_draft(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取人格草稿"""
    draft = await admin_config_service.get_draft(_CONFIG_KEY)
    return ApiResponse.ok(data=draft)


@router.put(
    "/persona/draft",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def save_persona_draft(
    body: PersonaDraftRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """保存人格草稿"""
    content_dict = body.content.model_dump()

    err = _validate_persona_content(content_dict)
    if err:
        return ApiResponse.fail(ADMIN_ERR_PERSONA_FIELD_EMPTY, message=err)

    result = await admin_config_service.save_draft(
        db, _CONFIG_KEY,
        json.dumps(content_dict, ensure_ascii=False),
        admin_user.username,
    )
    return ApiResponse.ok(data=result)


@router.delete(
    "/persona/draft",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def discard_persona_draft(
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """丢弃人格草稿"""
    ok = await admin_config_service.discard_draft(db, _CONFIG_KEY)
    if not ok:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD)
    return ApiResponse.ok(message="草稿已丢弃")


@router.post(
    "/persona/test",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def test_persona(
    body: PersonaTestRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """发布前测试人格配置"""
    content_dict = body.draft_content.model_dump()

    err = _validate_persona_content(content_dict)
    if err:
        return ApiResponse.fail(ADMIN_ERR_PERSONA_FIELD_EMPTY, message=err)

    result = await admin_config_service.run_standard_tests(
        db, _CONFIG_KEY,
        json.dumps(content_dict, ensure_ascii=False),
    )
    return ApiResponse.ok(data=result)


@router.post(
    "/persona/publish",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def publish_persona(
    body: PersonaPublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """发布人格配置（三道卡点全部执行）"""
    # 卡点一：确认文本
    if body.confirm_text != "CONFIRM":
        return ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID, message="请输入CONFIRM确认发布")

    # 卡点二：测试必须通过
    if not body.test_passed:
        return ApiResponse.fail(ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED, message="请先通过测试再发布")

    # 卡点三：字段非空
    content_dict = body.content.model_dump()
    err = _validate_persona_content(content_dict)
    if err:
        return ApiResponse.fail(ADMIN_ERR_PERSONA_FIELD_EMPTY, message=err)

    # 获取当前生效版本内容作为 before_value
    active_stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_KEY,
        AdminConfig.is_active == True,   # noqa: E712
        AdminConfig.is_draft == False,    # noqa: E712
    )
    active_result = await db.execute(active_stmt)
    active_config = active_result.scalars().first()
    before_value = active_config.config_value if active_config else None

    config_value = json.dumps(content_dict, ensure_ascii=False)
    result = await admin_config_service.publish_config(
        db=db,
        config_key=_CONFIG_KEY,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
    )
    return ApiResponse.ok(data=result)


@router.get(
    "/persona/history",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_persona_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """查询人格配置版本历史"""
    result = await admin_config_service.get_version_history(
        db, _CONFIG_KEY, page, page_size,
    )
    return ApiResponse.ok(data=result)


@router.get(
    "/persona/history/{version}",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_persona_history_detail(
    version: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取指定历史版本的完整人格内容（供管理端「查看」）"""
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
    "/persona/rollback",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def rollback_persona(
    body: PersonaRollbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """回滚人格配置到指定版本"""
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
