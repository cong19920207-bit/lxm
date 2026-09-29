# -*- coding: utf-8 -*-
# 统一时间线读路径（H5 / Open 共用，不经过 chat_service）

from typing import Any

from sqlalchemy import desc, select, func
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
    *,
    include_calls: bool = False,
    metrics=None,
    pending_reload: bool = False,
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

    if include_calls:
        from backend.models.realtime_voice import VoiceCall
        from backend.services.realtime_voice_card_service import CALL_FIELDS, timeline_call_item
        for item in merged:
            item.update({field: None for field in CALL_FIELDS})
        call_filter = (VoiceCall.user_id == user_id) & VoiceCall.sort_seq.is_not(None) & (
            VoiceCall.status.in_(['ended','missed'])) & VoiceCall.deletion_fence_at.is_(None) & VoiceCall.deleted_at.is_(None)
        call_scope = call_filter
        if cursor is not None:
            call_filter = call_filter & (VoiceCall.sort_seq < cursor)
        calls = (await db.scalars(select(VoiceCall).where(call_filter)
            .order_by(desc(VoiceCall.sort_seq)).limit(fetch_limit))).all()
        from backend.services.realtime_voice_crisis_presentation_service import crisis_presentations
        resources = await crisis_presentations(db, calls)
        for row in calls:
            item = timeline_call_item(row)
            item['crisis_resource'] = resources.get(row.call_id)
            merged.append(item)

    if include_calls and metrics is not None:
        events=[]
        if pending_reload:events.append(('voice.timeline.pending_reload',{},1))
        # Observe fetched rows and the requested anchor, never infer missing
        # items from integer gaps (other users/transactions can leave gaps).
        sequences=[item['sort_seq'] for item in merged]
        duplicates=len(sequences)-len(set(sequences))
        if duplicates:events.append(('voice.timeline.cursor_duplicate',{'scope':'page'},duplicates))
        if cursor is not None:
            anchors=0
            for model,scope in ((ConversationLog,ConversationLog.user_id==user_id),
                                (AgentMessage,AgentMessage.user_id==user_id),(VoiceCall,call_scope)):
                anchors+=await db.scalar(select(func.count()).select_from(model).where(scope,model.sort_seq==cursor))
            if anchors==0:events.append(('voice.timeline.cursor_missing',{'scope':'anchor'},1))
            elif anchors>1:events.append(('voice.timeline.cursor_duplicate',{'scope':'anchor'},1))
        await metrics.emit_many(events)

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
