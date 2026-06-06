# -*- coding: utf-8 -*-
# 统一时间线读路径（H5 / Open 共用，不经过 chat_service）

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog


def _timeline_conv_item(row: ConversationLog) -> dict[str, Any]:
    if row.role == "assistant":
        ds: str | None = None
        sk: bool | None = None
    else:
        ds = row.delivery_status
        sk = bool(row.skipped_in_prompt) if row.skipped_in_prompt is not None else False

    return {
        "source": row.role,
        "sort_seq": row.sort_seq,
        "id": row.id,
        "content": row.content,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "emotion_label": row.emotion_label,
        "is_read": None,
        "trigger_type": None,
        "delivery_status": ds,
        "skipped_in_prompt": sk,
    }


async def get_timeline(
    user_id: int,
    db: AsyncSession,
    cursor: int | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """与 GET /api/chat/timeline 响应 data 结构一致。"""
    fetch_limit = limit + 1

    conv_filter = ConversationLog.user_id == user_id
    if cursor is not None:
        conv_filter = conv_filter & (ConversationLog.sort_seq < cursor)
    conv_stmt = (
        select(ConversationLog)
        .where(conv_filter)
        .order_by(desc(ConversationLog.sort_seq))
        .limit(fetch_limit)
    )
    conv_rows = list((await db.execute(conv_stmt)).scalars().all())

    agent_filter = AgentMessage.user_id == user_id
    if cursor is not None:
        agent_filter = agent_filter & (AgentMessage.sort_seq < cursor)
    agent_stmt = (
        select(AgentMessage)
        .where(agent_filter)
        .order_by(desc(AgentMessage.sort_seq))
        .limit(fetch_limit)
    )
    agent_rows = list((await db.execute(agent_stmt)).scalars().all())

    merged: list[dict[str, Any]] = []
    for row in conv_rows:
        merged.append(_timeline_conv_item(row))
    for row in agent_rows:
        merged.append(
            {
                "source": "agent",
                "sort_seq": row.sort_seq,
                "id": row.id,
                "content": row.content,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "emotion_label": None,
                "is_read": row.is_read,
                "trigger_type": row.trigger_type,
                "delivery_status": None,
                "skipped_in_prompt": None,
            }
        )

    merged.sort(key=lambda x: x["sort_seq"], reverse=True)
    has_more = len(merged) > limit
    page_items = merged[:limit]
    page_items.reverse()
    next_cursor = page_items[0]["sort_seq"] if page_items and has_more else None

    return {
        "items": page_items,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
