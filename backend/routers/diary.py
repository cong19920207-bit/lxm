# -*- coding: utf-8 -*-
# AI 日记相关 API：日记列表、标记已读

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ERR_DIARY_NOT_FOUND
from backend.database import get_db
from backend.models.ai_diary import AiDiary
from backend.schemas.common import ApiResponse
from backend.schemas.diary import DiaryItem, DiaryListResponse
from backend.utils.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diary", tags=["日记"])


@router.get("/list", response_model=ApiResponse)
async def get_diary_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的日记列表（分页，按时间倒序）"""
    # 查询总数
    count_stmt = select(func.count()).select_from(AiDiary).where(
        AiDiary.user_id == user_id
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()

    # 分页查询
    offset = (page - 1) * page_size
    list_stmt = (
        select(AiDiary)
        .where(AiDiary.user_id == user_id)
        .order_by(AiDiary.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(list_stmt)
    diaries = result.scalars().all()

    items = [
        DiaryItem(
            id=d.id,
            content=d.content,
            relationship_level_at_creation=d.relationship_level_at_creation,
            is_read=d.is_read,
            created_at=d.created_at,
            covers_beijing_date=d.covers_beijing_date,
        )
        for d in diaries
    ]

    data = DiaryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )

    return ApiResponse.ok(data=data.model_dump())


@router.post("/{diary_id}/read", response_model=ApiResponse)
async def mark_diary_read(
    diary_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记单条日记为已读"""
    stmt = select(AiDiary).where(
        and_(
            AiDiary.id == diary_id,
            AiDiary.user_id == user_id,
        )
    )
    result = await db.execute(stmt)
    diary = result.scalar_one_or_none()

    if diary is None:
        return ApiResponse.fail(code=ERR_DIARY_NOT_FOUND)

    if not diary.is_read:
        diary.is_read = True
        await db.flush()

    return ApiResponse.ok()
