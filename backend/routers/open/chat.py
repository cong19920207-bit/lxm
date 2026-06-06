# -*- coding: utf-8 -*-
# Open API v1 对话路由

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.routers.chat import _execute_llm_bundle
from backend.schemas.common import ApiResponse
from backend.schemas.open_chat import OpenChatSendRequest
from backend.services.open_chat_service import open_get_timeline, open_resend, open_send
from backend.utils.open_api_auth import get_current_user_by_api_key

router = APIRouter(prefix="/api/open/v1/chat", tags=["open-chat"])


@router.post("/send")
async def open_chat_send(
    req: OpenChatSendRequest,
    user_id: int = Depends(get_current_user_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await open_send(user_id, db, req.content, _execute_llm_bundle)


@router.post("/resend")
async def open_chat_resend(
    user_id: int = Depends(get_current_user_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await open_resend(user_id, db, _execute_llm_bundle)


@router.get("/timeline")
async def open_chat_timeline(
    cursor: int | None = Query(None, description="游标 sort_seq"),
    limit: int = Query(20, ge=1, le=50),
    user_id: int = Depends(get_current_user_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    data = await open_get_timeline(user_id, db, cursor=cursor, limit=limit)
    return ApiResponse.ok(data=data)
