"""Read existing account diaries using the account's Open API Key."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ERR_DIARY_NOT_FOUND
from backend.database import get_db
from backend.routers.pet import private_response
from backend.schemas.common import ApiResponse
from backend.services import diary_reader
from backend.utils.open_api_auth import get_current_user_by_api_key

router = APIRouter(
    prefix="/api/open/v1/diary",
    tags=["open-diary"],
    dependencies=[Depends(private_response)],
)


@router.get("/list", response_model=ApiResponse)
async def get_diary_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user_id: int = Depends(get_current_user_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """列出账号已有日记；抓取列表不代表已经向用户展示正文。"""
    page_data = await diary_reader.list_diaries(db, user_id, page, page_size)
    data = page_data.model_dump()
    if page_data.total == 0:
        data["empty_state"] = await diary_reader.empty_diary_state(db, user_id)
    return ApiResponse.ok(data=data)


@router.post("/{diary_id}/read", response_model=ApiResponse)
async def mark_diary_read(
    diary_id: int,
    user_id: int = Depends(get_current_user_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    """正文已展示时，幂等同步本账号该篇日记的已读状态。"""
    if not await diary_reader.mark_read(db, user_id, diary_id):
        return ApiResponse.fail(code=ERR_DIARY_NOT_FOUND)
    await db.commit()
    return ApiResponse.ok()
