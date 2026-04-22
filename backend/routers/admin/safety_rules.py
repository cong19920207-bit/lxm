# -*- coding: utf-8 -*-
# 内容安全规则管理接口：违禁词、人格边界词、风格违规词的增删改查与导入

import json
import logging
from io import BytesIO

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.redis_client import get_redis
from backend.constants import (
    ADMIN_ERR_SAFETY_EXCEL_FILE_INVALID,
    ADMIN_ERR_SYSTEM_OPENPYXL_MISSING,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.utils.admin_auth import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_ROLES = ("super_admin", "ai_trainer")

# 三类关键词的 config_key
_BANNED_KEY = "banned_keywords"
_PERSONA_KEY = "persona_boundary_keywords"
_STYLE_KEY = "style_violation_keywords"


# ──────────────────── 请求模型 ────────────────────

class KeywordsUpdateRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1)


# ──────────────────── 辅助函数 ────────────────────

async def _update_keywords(
    db: AsyncSession,
    config_key: str,
    keywords: list[str],
    admin_user: AdminUser,
    request: Request,
) -> dict:
    """通用的关键词更新逻辑：发布配置 + 更新 Redis 缓存"""
    config_value = json.dumps(keywords, ensure_ascii=False)

    result = await admin_config_service.publish_config(
        db=db,
        config_key=config_key,
        config_value=config_value,
        admin_user=admin_user,
        request=request,
        target_description=f"更新安全规则 {config_key}",
    )

    # 同时更新 Redis 缓存
    redis = await get_redis()
    cache_key = f"active_config:{config_key}"
    await redis.set(cache_key, config_value)

    return result


# ──────────────────── 接口 ────────────────────

@router.get(
    "/safety-rules",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def get_safety_rules(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取所有安全规则关键词库"""
    banned = await admin_config_service.get_active_config(_BANNED_KEY)
    persona = await admin_config_service.get_active_config(_PERSONA_KEY)
    style = await admin_config_service.get_active_config(_STYLE_KEY)

    return ApiResponse.ok(data={
        "banned_keywords": banned if isinstance(banned, list) else [],
        "persona_boundary_keywords": persona if isinstance(persona, list) else [],
        "style_violation_keywords": style if isinstance(style, list) else [],
    })


@router.put(
    "/safety-rules/banned-keywords",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_banned_keywords(
    body: KeywordsUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """全量替换违禁词列表"""
    result = await _update_keywords(db, _BANNED_KEY, body.keywords, admin_user, request)
    return ApiResponse.ok(data=result)


@router.put(
    "/safety-rules/persona-keywords",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_persona_keywords(
    body: KeywordsUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """全量替换人格边界关键词列表"""
    result = await _update_keywords(db, _PERSONA_KEY, body.keywords, admin_user, request)
    return ApiResponse.ok(data=result)


@router.put(
    "/safety-rules/style-keywords",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def update_style_keywords(
    body: KeywordsUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """全量替换风格违规关键词列表"""
    result = await _update_keywords(db, _STYLE_KEY, body.keywords, admin_user, request)
    return ApiResponse.ok(data=result)


@router.post(
    "/safety-rules/banned-keywords/import",
    dependencies=[require_role(*_ALLOWED_ROLES)],
)
async def import_banned_keywords(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """从 Excel 文件导入违禁词（与现有词库合并去重）"""
    # 校验文件类型
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        return ApiResponse.fail(ADMIN_ERR_SAFETY_EXCEL_FILE_INVALID, message="请上传 .xlsx 或 .xls 格式的 Excel 文件")

    try:
        import openpyxl
    except ImportError:
        return ApiResponse.fail(ADMIN_ERR_SYSTEM_OPENPYXL_MISSING)

    # 读取 Excel 文件
    try:
        content = await file.read()
        wb = openpyxl.load_workbook(BytesIO(content), read_only=True)
        ws = wb.active

        imported_keywords = []
        for row in ws.iter_rows(min_col=1, max_col=1, values_only=True):
            val = row[0]
            if val is not None:
                keyword = str(val).strip()
                if keyword:
                    imported_keywords.append(keyword)
        wb.close()
    except Exception as e:
        logger.error("解析 Excel 文件失败: %s", str(e))
        return ApiResponse.fail(ADMIN_ERR_SAFETY_EXCEL_FILE_INVALID, message=f"Excel 文件解析失败：{str(e)}")

    if not imported_keywords:
        return ApiResponse.fail(ADMIN_ERR_SAFETY_EXCEL_FILE_INVALID, message="Excel 文件中未找到有效关键词")

    imported_count = len(imported_keywords)

    # 读取现有词库并合并去重
    existing = await admin_config_service.get_active_config(_BANNED_KEY)
    if not isinstance(existing, list):
        existing = []

    merged = list(set(existing + imported_keywords))
    merged.sort()

    # 保存合并后的词库
    await _update_keywords(db, _BANNED_KEY, merged, admin_user, request)

    return ApiResponse.ok(data={
        "imported_count": imported_count,
        "total_count": len(merged),
    })
