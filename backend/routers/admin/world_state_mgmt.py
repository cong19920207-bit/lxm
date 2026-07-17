# -*- coding: utf-8 -*-
# 世界观管理接口：世界观配置读写 + 世界状态历史查看

import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.admin_config import AdminConfig
from backend.models.admin_user import AdminUser
from backend.models.world_state import WorldState
from backend.schemas.common import ApiResponse
from backend.services.admin_config_service import admin_config_service
from backend.utils.admin_auth import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_CONFIG_KEY = "world_state_config"
_READ_ROLES = ("super_admin", "ai_trainer", "observer")
_WRITE_ROLES = ("super_admin", "ai_trainer")


class WorldStateConfigRequest(BaseModel):
    event_trigger_enabled: bool
    fallback_interval_days: int = Field(..., ge=1, le=7)
    min_dialog_rounds: int = Field(..., ge=1, le=20)


@router.get(
    "/world-state/config",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_world_state_config(
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取当前世界观配置"""
    data = await admin_config_service.get_active_config(_CONFIG_KEY)
    return ApiResponse.ok(data=data)


@router.put(
    "/world-state/config",
    dependencies=[require_role(*_WRITE_ROLES)],
)
async def update_world_state_config(
    body: WorldStateConfigRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """更新世界观配置并直接发布"""
    # 获取当前配置值作为 before_value
    active_stmt = select(AdminConfig).where(
        AdminConfig.config_key == _CONFIG_KEY,
        AdminConfig.is_active == True,   # noqa: E712
        AdminConfig.is_draft == False,    # noqa: E712
    )
    active_result = await db.execute(active_stmt)
    active_record = active_result.scalars().first()
    before_value = active_record.config_value if active_record else None

    config_value = json.dumps(body.model_dump(), ensure_ascii=False)

    result = await admin_config_service.publish_config(
        db=db,
        config_key=_CONFIG_KEY,
        config_value=config_value,
        admin_user=admin_user,
        before_value=before_value,
        request=request,
        target_description="更新世界观配置",
    )
    return ApiResponse.ok(data=result)


@router.get(
    "/world-state/history",
    dependencies=[require_role(*_READ_ROLES)],
)
async def get_world_state_history(
    user_id: int | None = Query(None, description="用户 ID（可选筛选）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """查询世界状态历史记录（只读，来源 world_state 表）"""
    conditions = []
    if user_id is not None:
        conditions.append(WorldState.user_id == user_id)

    count_stmt = select(func.count(WorldState.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    query_stmt = (
        select(WorldState)
        .order_by(WorldState.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if conditions:
        query_stmt = query_stmt.where(*conditions)
    result = await db.execute(query_stmt)
    records = result.scalars().all()

    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "list": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "content": r.content,
                "trigger_conversation_id": r.trigger_conversation_id,
                "relevance_weight": r.relevance_weight,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }
    return ApiResponse.ok(data=data)
