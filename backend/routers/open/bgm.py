"""Published background music for clients using an existing account API Key."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.routers.bgm import read_catalog
from backend.routers.pet import private_response
from backend.schemas.common import ApiResponse
from backend.utils.open_api_auth import get_current_user_by_api_key

router = APIRouter(
    prefix="/api/open/v1/bgm",
    tags=["open-bgm"],
    dependencies=[Depends(get_current_user_by_api_key), Depends(private_response)],
)


@router.get("/catalog", response_model=ApiResponse, responses={503: {"model": ApiResponse}})
async def get_catalog(response: Response, db: AsyncSession = Depends(get_db)):
    """列出已发布的背景音乐、默认曲目与可直接播放的 HTTPS 地址。"""
    # Authentication may hold a connection. The shared catalog cache opens its own.
    await db.close()
    return await read_catalog(response, db)
