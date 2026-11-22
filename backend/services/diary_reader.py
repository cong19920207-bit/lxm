"""Account-scoped access to existing diaries for H5 and Open API clients."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ai_diary import AiDiary
from backend.models.relationship import Relationship
from backend.schemas.diary import DiaryItem, DiaryListResponse


async def list_diaries(
    db: AsyncSession, user_id: int, page: int, page_size: int
) -> DiaryListResponse:
    owned = AiDiary.user_id == user_id
    total = await db.scalar(select(func.count()).select_from(AiDiary).where(owned))
    data = DiaryListResponse(total=total, page=page, page_size=page_size)
    offset = (page - 1) * page_size
    if offset < total:
        rows = await db.scalars(
            select(AiDiary)
            .where(owned)
            .order_by(AiDiary.created_at.desc(), AiDiary.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        data.items = [DiaryItem.model_validate(row, from_attributes=True) for row in rows]
    return data


async def empty_diary_state(db: AsyncSession, user_id: int) -> dict[str, str]:
    """Match H5's empty bookshelf, without creating a missing relationship."""
    level = await db.scalar(select(Relationship.level).where(Relationship.user_id == user_id))
    if level is not None and level >= 1:
        return {"kind": "active", "message": "今天林小梦还没写新日记哦\n多和我聊聊吧"}
    return {"kind": "new", "message": "和我多聊聊天\n我会把我们的故事都记下来"}


async def mark_read(db: AsyncSession, user_id: int, diary_id: int) -> bool:
    """Return the same outcome for another user's diary and a missing ID."""
    diary = await db.scalar(
        select(AiDiary).where(AiDiary.id == diary_id, AiDiary.user_id == user_id)
    )
    if diary is None:
        return False
    if not diary.is_read:
        diary.is_read = True
        await db.flush()
    return True
