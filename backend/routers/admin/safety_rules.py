# -*- coding: utf-8 -*-
# 内容安全规则管理接口：违禁词、人格边界词、风格违规词的增删改查与导入

import json
import logging
from io import BytesIO

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.admin_user import AdminUser
from backend.redis_client import get_redis
from backend.constants import (
    ADMIN_ERR_SAFETY_EXCEL_FILE_INVALID,
    ADMIN_ERR_SYSTEM_OPENPYXL_MISSING,
    ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID,
    ADMIN_ERR_VOICE_CONFIG_NOT_FOUND,
    ADMIN_ERR_VOICE_CONFIG_PUBLISH_FAILED,
    ADMIN_ERR_VOICE_CRISIS_KEYWORDS_INVALID,
)
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.services.realtime_voice_crisis_config_service import CrisisConfigReader
from backend.services.realtime_voice_config_service import (
    VoiceConfigError,
    audit_crisis_operation_failure,
    publish_crisis_keywords_atomically,
    rollback_crisis_keywords_atomically,
)
from backend.utils.admin_auth import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_READ_ROLES = ("super_admin", "ai_trainer", "observer")
_WRITE_ROLES = ("super_admin", "ai_trainer")

# 三类关键词的 config_key
_BANNED_KEY = "banned_keywords"
_PERSONA_KEY = "persona_boundary_keywords"
_STYLE_KEY = "style_violation_keywords"
_CRISIS_KEY = "crisis_keywords"


# ──────────────────── 请求模型 ────────────────────

class KeywordsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keywords: list[str]


class CrisisRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(..., ge=1)
    confirm_text: str


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
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_safety_rules(
    admin_user: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取所有安全规则关键词库"""
    banned = await admin_config_service.get_active_config(_BANNED_KEY)
    persona = await admin_config_service.get_active_config(_PERSONA_KEY)
    style = await admin_config_service.get_active_config(_STYLE_KEY)
    crisis, crisis_status = await CrisisConfigReader(
        session_factory=None, redis_provider=get_redis).inspect(db=db)

    return ApiResponse.ok(data={
        "banned_keywords": banned if isinstance(banned, list) else [],
        "persona_boundary_keywords": persona if isinstance(persona, list) else [],
        "style_violation_keywords": style if isinstance(style, list) else [],
        "crisis_keywords": crisis if isinstance(crisis, list) else [],
        "crisis_keywords_status": crisis_status,
    })


@router.put(
    "/safety-rules/crisis-keywords",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def update_crisis_keywords(
    body: KeywordsUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """规范化发布独立危机词；DB/Redis 失败时补偿旧状态。"""
    try:
        result = await publish_crisis_keywords_atomically(
            db,
            keywords=body.keywords,
            admin_user=admin_user,
            request=request,
        )
    except VoiceConfigError as exc:
        payload = ApiResponse.fail(
            ADMIN_ERR_VOICE_CRISIS_KEYWORDS_INVALID,
            message=exc.message,
            data={"error_code": exc.code},
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))
    except Exception:
        logger.exception("发布 crisis_keywords 失败，已执行补偿")
        payload = ApiResponse.fail(ADMIN_ERR_VOICE_CONFIG_PUBLISH_FAILED)
        return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))
    return ApiResponse.ok(data=result)


@router.get(
    "/safety-rules/crisis-keywords/history",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_crisis_keywords_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    result = await admin_config_service.get_version_history(
        db, _CRISIS_KEY, page, page_size,
    )
    return ApiResponse.ok(data=result)


@router.post(
    "/safety-rules/crisis-keywords/rollback",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def rollback_crisis_keywords(
    body: CrisisRollbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    if body.confirm_text != "CONFIRM":
        error = VoiceConfigError(
            "VOICE_CONFIG_CONFIRM_TEXT_INVALID",
            "必须精确输入 CONFIRM",
        )
        await audit_crisis_operation_failure(
            db,
            action="rollback",
            error=error,
            admin_user=admin_user,
            request=request,
            target_version=body.version,
        )
        payload = ApiResponse.fail(ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID)
        return JSONResponse(status_code=400, content=payload.model_dump(mode="json"))
    try:
        result = await rollback_crisis_keywords_atomically(
            db,
            version=body.version,
            admin_user=admin_user,
            request=request,
        )
    except VoiceConfigError as exc:
        error_code = (
            ADMIN_ERR_VOICE_CONFIG_NOT_FOUND
            if exc.status_code == 404
            else ADMIN_ERR_VOICE_CRISIS_KEYWORDS_INVALID
        )
        payload = ApiResponse.fail(
            error_code,
            message=exc.message,
            data={"error_code": exc.code},
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))
    except Exception:
        logger.exception("回滚 crisis_keywords 失败，已执行补偿")
        payload = ApiResponse.fail(ADMIN_ERR_VOICE_CONFIG_PUBLISH_FAILED)
        return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))
    return ApiResponse.ok(data=result)


@router.put(
    "/safety-rules/banned-keywords",
    dependencies=[require_role(*_WRITE_ROLES)],
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
    dependencies=[require_role(*_WRITE_ROLES)],
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
    dependencies=[require_role(*_WRITE_ROLES)],
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
    dependencies=[require_role(*_WRITE_ROLES)],
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
