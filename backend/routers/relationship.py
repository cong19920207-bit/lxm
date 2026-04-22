# -*- coding: utf-8 -*-
# 关系相关 API：关系等级、成长值查询、关系状态详情

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services.relationship_service import RelationshipService
from backend.utils.auth_middleware import get_current_user

router = APIRouter(prefix="/api/relationship", tags=["关系"])


@router.get("/status", response_model=ApiResponse)
async def get_relationship_status(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的关系状态"""
    svc = RelationshipService(db)
    info = await svc.get_relationship_info(user_id)
    return ApiResponse.ok(data=info)


@router.get("/history", response_model=ApiResponse)
async def get_relationship_history(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取关系成长历史记录（今日各行为成长值明细）"""
    svc = RelationshipService(db)
    history = await svc.get_growth_history(user_id)
    return ApiResponse.ok(data=history)


@router.get("/detail", response_model=ApiResponse)
async def get_relationship_detail(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取关系状态页所需的完整数据"""
    svc = RelationshipService(db)
    detail = await svc.get_relationship_detail(user_id)
    return ApiResponse.ok(data=detail)


@router.get("/growth-log", response_model=ApiResponse)
async def get_growth_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取成长值获取记录（分页）"""
    svc = RelationshipService(db)
    data = await svc.get_growth_log_paginated(user_id, page, page_size)
    return ApiResponse.ok(data=data)
