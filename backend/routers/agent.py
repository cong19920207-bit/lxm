# -*- coding: utf-8 -*-
# 主动消息相关 API：未读消息列表、单条标记已读、未读计数

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ERR_AGENT_MSG_NOT_FOUND
from backend.database import get_db
from backend.models.agent_message import AgentMessage
from backend.schemas.common import ApiResponse
from backend.utils.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["主动消息"])


@router.get("/messages")
async def get_agent_messages(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/agent/messages
    获取该用户所有未读主动消息，按 created_at 倒序
    """
    stmt = (
        select(AgentMessage)
        .where(
            and_(
                AgentMessage.user_id == user_id,
                AgentMessage.is_read == False,  # noqa: E712
            )
        )
        .order_by(desc(AgentMessage.created_at))
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    data = [
        {
            "id": msg.id,
            "trigger_type": msg.trigger_type,
            "content": msg.content,
            "action_score": msg.action_score,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
        for msg in messages
    ]

    return ApiResponse.ok(data=data)


@router.post("/messages/{message_id}/read")
async def mark_message_read(
    message_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/agent/messages/{message_id}/read
    仅标记指定的单条消息为已读，严格只改这一条
    """
    stmt = select(AgentMessage).where(
        and_(
            AgentMessage.id == message_id,
            AgentMessage.user_id == user_id,
        )
    )
    result = await db.execute(stmt)
    msg = result.scalar_one_or_none()

    if not msg:
        return ApiResponse.fail(ERR_AGENT_MSG_NOT_FOUND)

    if msg.is_read:
        return ApiResponse.ok(message="消息已标记为已读")

    msg.is_read = True
    await db.flush()

    return ApiResponse.ok(message="标记成功")


@router.get("/unread-count")
async def get_unread_count(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/agent/unread-count
    返回该用户当前未读主动消息总数
    """
    stmt = (
        select(func.count())
        .select_from(AgentMessage)
        .where(
            and_(
                AgentMessage.user_id == user_id,
                AgentMessage.is_read == False,  # noqa: E712
            )
        )
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0

    return ApiResponse.ok(data={"count": count})
