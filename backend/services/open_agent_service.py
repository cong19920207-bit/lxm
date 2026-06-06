# -*- coding: utf-8 -*-
# Open API Agent Facade（与 H5 /api/agent 数据一致）

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ERR_AGENT_MSG_NOT_FOUND
from backend.models.agent_message import AgentMessage
from backend.schemas.common import ApiResponse


async def list_unread_messages(user_id: int, db: AsyncSession) -> list[dict]:
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
    messages = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": msg.id,
            "trigger_type": msg.trigger_type,
            "content": msg.content,
            "action_score": msg.action_score,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
        for msg in messages
    ]


async def mark_message_read(user_id: int, message_id: int, db: AsyncSession) -> ApiResponse:
    stmt = select(AgentMessage).where(
        and_(
            AgentMessage.id == message_id,
            AgentMessage.user_id == user_id,
        )
    )
    msg = (await db.execute(stmt)).scalar_one_or_none()
    if not msg:
        return ApiResponse.fail(ERR_AGENT_MSG_NOT_FOUND)
    if msg.is_read:
        return ApiResponse.ok(message="消息已标记为已读")
    msg.is_read = True
    await db.flush()
    return ApiResponse.ok(message="标记成功")


async def get_unread_count(user_id: int, db: AsyncSession) -> int:
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
    return (await db.execute(stmt)).scalar() or 0
