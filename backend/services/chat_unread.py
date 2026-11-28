"""Account inbox shared by H5 and Open API."""
from typing import Literal

from sqlalchemy import func, literal, select, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog

MessageSource = Literal["assistant", "agent"]


def _unread_queries(user_id: int):
    reply, agent = ConversationLog, AgentMessage
    return (
        select(literal("assistant").label("source"), reply.id, reply.sort_seq).where(
            reply.user_id == user_id, reply.reply_is_read.is_(False), reply.role == "assistant"),
        select(literal("agent").label("source"), agent.id, agent.sort_seq).where(
            agent.user_id == user_id, agent.is_read.is_(False)),
    )


async def unread_summary(db: AsyncSession, user_id: int) -> dict:
    pending = union_all(*_unread_queries(user_id)).cte("unread_messages")
    seq = pending.c.sort_seq
    bounds = select(func.count().label("total"), func.min(seq).label("first_seq"),
                    func.max(seq).label("last_seq")).select_from(pending).subquery()
    # One snapshot for the total and both anchors, including an empty inbox.
    rows = (await db.execute(select(bounds.c.total, pending).select_from(
        bounds.outerjoin(pending, seq.in_([bounds.c.first_seq, bounds.c.last_seq]))
    ).order_by(seq, pending.c.source, pending.c.id))).all()

    def anchor(row):
        return dict(source=row.source, id=row.id, sort_seq=str(row.sort_seq)) if row.id is not None else None

    return dict(count=rows[0].total, first_unread=anchor(rows[0]), latest_unread=anchor(rows[-1]))


async def unread_among(db: AsyncSession, user_id: int, assistant_ids: list[int], agent_ids: list[int]) -> list[dict]:
    replies, agents = _unread_queries(user_id)
    selected = union_all(replies.where(ConversationLog.id.in_(assistant_ids)),
                         agents.where(AgentMessage.id.in_(agent_ids))).subquery()
    rows = await db.execute(select(selected.c.source, selected.c.id))
    return [dict(row) for row in rows.mappings()]


async def mark_message_read(db: AsyncSession, user_id: int, source: MessageSource,
                            message_id: int) -> Literal["read", "already_read", "missing"]:
    if source == "assistant":
        model, field = ConversationLog, ConversationLog.reply_is_read
        scope = (model.user_id == user_id, model.id == message_id, model.role == "assistant")
    else:
        model, field = AgentMessage, AgentMessage.is_read
        scope = (model.user_id == user_id, model.id == message_id)
    changed = await db.execute(update(model).where(*scope, field.is_(False)).values({field: True}))
    if changed.rowcount:
        return "read"
    if await db.scalar(select(model.id).where(*scope)) is None:
        return "missing"
    return "already_read"
