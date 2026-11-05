"""Award chat bonuses from committed conversation facts, in one SQL transaction."""
import asyncio
from datetime import date, datetime, time, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_maker
from backend.models.agent_message import AgentMessage
from backend.models.conversation_log import ConversationLog
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.models.relationship_level_history import RelationshipLevelHistory
from backend.models.user import User
from backend.services.relationship_service import GROWTH_ACTIONS, RelationshipService, _calc_level

CHAT_BONUS_ACTIONS = ('long_session', 'reply_agent')
BEIJING = ZoneInfo('Asia/Shanghai')
DEEP_CHAT_SECONDS = 600
SESSION_GAP_SECONDS = 300
logger = logging.getLogger(__name__)


async def settle_chat_rewards(user_id: int, round_id: str, *, sessions=None) -> dict[str, int]:
    """Retry the entire bonus transaction after MySQL deadlock/lock timeout.

    Different users can collide on missing source-key index gaps despite their
    independent user locks. Never retry the older dialog/Redis side effects.
    """
    sessions = sessions or async_session_maker
    for attempt in range(3):
        try:
            async with sessions() as db:
                earned = await award_chat_rewards(db, user_id, round_id)
                await db.commit()
                return earned
        except DBAPIError as error:
            code = getattr(error.orig, 'args', (None,))[0]
            if code not in (1213, 1205) or attempt == 2:
                raise
            logger.warning('聊天奖励事务重试: user_id=%d round_id=%s mysql_code=%s attempt=%d',
                user_id, round_id, code, attempt+1)
            await asyncio.sleep(.05 * (attempt+1))


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, BEIJING).astimezone(timezone.utc).replace(tzinfo=None)
    return start, start + timedelta(days=1)


async def chat_reward_totals(db: AsyncSession, user_id: int, day: date, *, for_update=False) -> dict[str, int]:
    """SQL is authoritative for these bonuses, including legacy untagged rows."""
    start, end = _day_bounds(day)
    query = select(RelationshipGrowthLog.action_type, RelationshipGrowthLog.points).where(
        RelationshipGrowthLog.user_id == user_id,
        RelationshipGrowthLog.action_type.in_(CHAT_BONUS_ACTIONS),
        or_(RelationshipGrowthLog.business_date == day,
            (RelationshipGrowthLog.business_date.is_(None)) &
            (RelationshipGrowthLog.created_at >= start) & (RelationshipGrowthLog.created_at < end)),
    )
    # Callers hold the user lock. A current read also handles sessions whose
    # MySQL repeatable-read snapshot predates another reward transaction.
    if for_update:
        query = query.with_for_update()
    totals = dict.fromkeys(CHAT_BONUS_ACTIONS, 0)
    for action, points in await db.execute(query):
        totals[action] += points
    return totals


async def _deep_chat_reached(db, user_id, last_seq, last_input_at, day):
    day_start, _ = _day_bounds(day)
    # At most the preceding 15 minutes are needed to prove a connected
    # 10-minute span when every adjacent gap is at most five minutes.
    lower = max(day_start, last_input_at - timedelta(seconds=DEEP_CHAT_SECONDS + SESSION_GAP_SECONDS))
    moments = (await db.execute(select(func.max(ConversationLog.created_at)).where(
        ConversationLog.user_id == user_id,
        ConversationLog.role == 'user',
        ConversationLog.delivery_status == 'delivered',
        ConversationLog.skipped_in_prompt.is_(False),
        ConversationLog.round_id.is_not(None),
        ConversationLog.sort_seq <= last_seq,
        ConversationLog.created_at >= lower,
        ConversationLog.created_at <= last_input_at,
    ).group_by(ConversationLog.round_id).order_by(func.max(ConversationLog.sort_seq)))).scalars().all()
    start = previous = None
    for moment in moments:
        if previous is None or not 0 <= (moment - previous).total_seconds() <= SESSION_GAP_SECONDS:
            start = moment
        previous = moment
    return start is not None and (last_input_at - start).total_seconds() >= DEEP_CHAT_SECONDS


async def award_chat_rewards(db: AsyncSession, user_id: int, round_id: str) -> dict[str, int]:
    """Only successful rounds earn; caller commits/rolls back points and logs together.

    A reply consumes the latest proactive message between the previous successful
    round and this round's last user input. Read/unread is deliberately irrelevant.
    Multiple proactive bubbles before one response count as one response.
    """
    earned = dict.fromkeys(CHAT_BONUS_ACTIONS, 0)
    if not round_id:
        return earned
    # Match the existing text/voice scalar lock order: user, then relationship.
    if await db.scalar(select(User.id).where(User.id == user_id).with_for_update()) is None:
        return earned
    inputs = (await db.execute(select(ConversationLog.sort_seq, ConversationLog.created_at).where(
        ConversationLog.user_id == user_id, ConversationLog.round_id == round_id,
        ConversationLog.role == 'user', ConversationLog.delivery_status == 'delivered',
        ConversationLog.skipped_in_prompt.is_(False),
    ).order_by(ConversationLog.sort_seq).with_for_update())).all()
    completed_at = await db.scalar(select(func.max(ConversationLog.created_at)).where(
        ConversationLog.user_id == user_id, ConversationLog.round_id == round_id,
        ConversationLog.role == 'assistant'))
    if not inputs or completed_at is None:
        return earned
    first_seq, last_seq = inputs[0].sort_seq, inputs[-1].sort_seq
    last_input_at = inputs[-1].created_at
    day = completed_at.replace(tzinfo=timezone.utc).astimezone(BEIJING).date()
    rel = await RelationshipService(db)._get_or_create_relationship(user_id)
    totals = await chat_reward_totals(db, user_id, day, for_update=True)
    candidates = []
    if totals['long_session'] < GROWTH_ACTIONS['long_session']['daily_limit']:
        if await _deep_chat_reached(db, user_id, last_seq, last_input_at, day):
            candidates.append(('long_session', 'chat_session', f'{user_id}:{day.isoformat()}'))

    if totals['reply_agent'] < GROWTH_ACTIONS['reply_agent']['daily_limit']:
        # A successful round ends at its last committed assistant bubble.
        previous_reply_seq = await db.scalar(select(func.max(ConversationLog.sort_seq)).where(
            ConversationLog.user_id == user_id, ConversationLog.role == 'assistant',
            ConversationLog.round_id.is_not(None), ConversationLog.round_id != round_id,
            ConversationLog.sort_seq < first_seq))
        agent_id = await db.scalar(select(AgentMessage.id).where(
            AgentMessage.user_id == user_id, AgentMessage.sort_seq > (previous_reply_seq or 0),
            AgentMessage.sort_seq < last_seq,
        ).order_by(AgentMessage.sort_seq.desc()).limit(1))
        if agent_id is not None:
            candidates.append(('reply_agent', 'agent_reply', str(agent_id)))

    for action, source_type, source_id in candidates:
        previous = await db.scalar(select(RelationshipGrowthLog.id).where(
            RelationshipGrowthLog.source_type == source_type,
            RelationshipGrowthLog.source_id == source_id).with_for_update())
        if previous is not None:
            continue
        points = min(GROWTH_ACTIONS[action]['points'], GROWTH_ACTIONS[action]['daily_limit'] - totals[action])
        db.add(RelationshipGrowthLog(user_id=user_id, action_type=action, points=points,
            source_type=source_type, source_id=source_id, business_date=day, created_at=completed_at))
        earned[action] = points

    if sum(earned.values()):
        old_level = rel.level
        rel.growth_value += sum(earned.values())
        rel.last_interaction_at = max(rel.last_interaction_at or completed_at, completed_at)
        new_level = _calc_level(rel.growth_value)
        if new_level > old_level:
            rel.level = new_level
            db.add(RelationshipLevelHistory(user_id=user_id, from_level=old_level,
                to_level=new_level, achieved_at=completed_at))
        await db.flush()
    return earned
