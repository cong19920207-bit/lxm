# -*- coding: utf-8 -*-
# Open API v1 主动消息路由

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.common import ApiResponse
from backend.services.open_agent_service import (
    get_unread_count,
    list_unread_messages,
    mark_message_read,
)
from backend.utils.open_api_auth import get_current_user_by_api_key

router = APIRouter(prefix="/api/open/v1/agent", tags=["open-agent"])


@router.get("/messages")
async def open_agent_messages(
    user_id: int = Depends(get_current_user_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    data = await list_unread_messages(user_id, db)
    return ApiResponse.ok(data=data)


@router.get("/unread-count")
async def open_agent_unread_count(
    user_id: int = Depends(get_current_user_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    count = await get_unread_count(user_id, db)
    return ApiResponse.ok(data={"count": count})


@router.post("/messages/{message_id}/read")
async def open_agent_mark_read(
    message_id: int,
    user_id: int = Depends(get_current_user_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await mark_message_read(user_id, message_id, db)
