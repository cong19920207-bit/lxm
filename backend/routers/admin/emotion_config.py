# -*- coding: utf-8 -*-
# 情绪配置管理接口：查看与更新 7 种情绪的配置

import json
import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ADMIN_ERR_EMOTION_CONFIG_INVALID
from backend.database import get_db
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.utils.admin_auth import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_CONFIG_KEY = "emotion_config"
_READ_ROLES = ("super_admin", "ai_trainer", "observer")
_WRITE_ROLES = ("super_admin", "ai_trainer")

VALID_EMOTIONS = ("平静", "开心", "好奇", "想念", "担心", "害羞", "困倦")


class EmotionUpdateRequest(BaseModel):
    trigger_rule: str = Field(..., min_length=1)
    status_texts: list[str]
    avatar_id: str = Field(..., min_length=1)


@router.get(
    "/emotion-config",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_emotion_config(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取当前生效的情绪配置"""
    data = await admin_config_service.get_active_config(_CONFIG_KEY)
    return ApiResponse.ok(data=data)


@router.put(
    "/emotion-config/{emotion_name}",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def update_emotion_config(
    emotion_name: str,
    body: EmotionUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新单个情绪配置并直接发布（无需测试卡点和 CONFIRM）"""
    if emotion_name not in VALID_EMOTIONS:
        return ApiResponse.fail(
            ADMIN_ERR_EMOTION_CONFIG_INVALID,
            message=f"无效的情绪名称，必须是：{'、'.join(VALID_EMOTIONS)}",
        )

    if not (3 <= len(body.status_texts) <= 5):
        return ApiResponse.fail(
            ADMIN_ERR_EMOTION_CONFIG_INVALID,
            message="status_texts 长度须为 3-5 条",
        )

    for idx, text in enumerate(body.status_texts):
        if len(text) > 50:
            return ApiResponse.fail(
                ADMIN_ERR_EMOTION_CONFIG_INVALID,
                message=f"第 {idx + 1} 条文案超过 50 字",
            )

    # 读取当前完整配置
    current_config = await admin_config_service.get_active_config(_CONFIG_KEY)
    if not isinstance(current_config, dict):
        current_config = {}

    # 获取当前配置值作为 before_value
    active_stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_KEY,
        AdminConfig.is_active == True,   # noqa: E712
        AdminConfig.is_draft == False,    # noqa: E712
    )
    active_result = await db.execute(active_stmt)
    active_record = active_result.scalars().first()
    before_value = active_record.config_value if active_record else None

    # 更新对应情绪的配置
    current_config[emotion_name] = {
        "trigger_rule": body.trigger_rule,
        "status_texts": body.status_texts,
        "avatar_id": body.avatar_id,
    }

    config_value = json.dumps(current_config, ensure_ascii=False)

    result = await admin_config_service.publish_config(
        db=db,
        config_key=_CONFIG_KEY,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description=f"更新情绪配置：{emotion_name}",
    )
    return ApiResponse.ok(data=result)
