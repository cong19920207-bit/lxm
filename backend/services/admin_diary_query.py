# -*- coding: utf-8 -*-
# 管理端 AI 日记列表：与 diary-history、用户详情子资源共用查询逻辑，避免双入口数据不一致

from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ai_diary import AiDiary
from backend.models.user import User
from backend.schemas.common import ApiResponse
from backend.services.admin_date_filter import append_created_at_range, parse_admin_date_range


async def fetch_admin_diary_list_page(
    db: AsyncSession,
    *,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Optional[ApiResponse], Optional[dict]]:
    """
    管理端日记分页列表（只读）。
    与 GET /api/admin/diary-history 使用相同筛选语义，供用户详情 GET /users/{id}/diaries 复用。

    :param user_id: 若指定则仅该用户；None 表示不按用户过滤（全站日记历史）
    :return: (错误时 ApiResponse, None) 或 (None, data 字典)
    """
    start_dt, end_exclusive, date_err = parse_admin_date_range(start_date, end_date)
    if date_err is not None:
        return date_err, None

    filters = []
    if user_id is not None:
        filters.append(AiDiary.user_id == user_id)
    append_created_at_range(filters, AiDiary.created_at, start_dt, end_exclusive)

    where_clause = and_(*filters) if filters else True

    count_stmt = select(func.count()).select_from(AiDiary).where(where_clause)
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * page_size
    list_stmt = (
        select(AiDiary, User.username)
        .join(User, User.id == AiDiary.user_id)
        .where(where_clause)
        .order_by(AiDiary.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    list_result = await db.execute(list_stmt)
    list_rows = list_result.all()

    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "list": [
            {
                "id": diary.id,
                "user_id": diary.user_id,
                "username": username,
                "content": diary.content,
                "relationship_level_at_creation": diary.relationship_level_at_creation,
                "is_read": diary.is_read,
                "created_at": diary.created_at.isoformat() if diary.created_at else None,
                "covers_beijing_date": diary.covers_beijing_date.isoformat()
                if diary.covers_beijing_date
                else None,
            }
            for diary, username in list_rows
        ],
    }
    return None, data
