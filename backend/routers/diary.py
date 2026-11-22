# -*- coding: utf-8 -*-
# AI 日记相关 API：日记列表、标记已读

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ERR_DIARY_NOT_FOUND
from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services import diary_reader
from backend.utils.auth_middleware import get_current_user

router = APIRouter(prefix="/api/diary", tags=["日记"])


@router.get("/list", response_model=ApiResponse)
async def get_diary_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的日记列表（分页，按时间倒序）"""
    data = await diary_reader.list_diaries(db, user_id, page, page_size)
    return ApiResponse.ok(data=data.model_dump())


@router.post("/{diary_id}/read", response_model=ApiResponse)
async def mark_diary_read(
    diary_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记单条日记为已读"""
    if not await diary_reader.mark_read(db, user_id, diary_id):
        return ApiResponse.fail(code=ERR_DIARY_NOT_FOUND)
    await db.commit()
    return ApiResponse.ok()
