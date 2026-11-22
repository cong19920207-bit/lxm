"""Read completed logical turns in business order without modifying historical rows."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from backend.models.chat_lifecycle import ChatGeneration, ChatGenerationMessage, ChatMessageState
from backend.models.conversation_log import ConversationLog as Log


HISTORY_ZONE = ZoneInfo("Asia/Shanghai")
HISTORY_TITLE = "【最近对话】"
ROUND_LIMIT = 30


def local_time(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(HISTORY_ZONE)


@dataclass(frozen=True)
class HistoryMessage:
    id: int
    role: str
    content: str
    created_at: datetime | None
    sort_seq: int

    def render(self):
        local = local_time(self.created_at)
        stamp = local.strftime("%Y-%m-%d %H:%M:%S") if local else "时间未记录"
        speaker = "用户" if self.role == "user" else "林小梦"
        body = json.dumps(self.content, ensure_ascii=False)
        for char in "【】<>\u2028\u2029\u0085":
            body = body.replace(char, f"\\u{ord(char):04x}")
        return f"[{stamp}] {speaker}：{body}"


@dataclass(frozen=True)
class CompletedRound:
    key: str
    source: str
    messages: tuple[HistoryMessage, ...]

    @property
    def message_ids(self):
        return tuple(m.id for m in self.messages)


@dataclass(frozen=True)
class HistoryCandidates:
    rounds: tuple[CompletedRound, ...]
    excluded_fragments: int


def _turn(key, source, rows):
    roles = [row.role for row in rows]
    if not roles or roles[0] != "user" or roles[-1] != "assistant":
        return None
    if any(role != "assistant" for role in roles[roles.index("assistant"):]):
        return None
    return CompletedRound(key, source, tuple(
        HistoryMessage(r.id, r.role, r.content, r.created_at, r.sort_seq) for r in rows))


def _eligible(row, excluded):
    return (row.id not in excluded and row.role in ("user", "assistant")
            and row.delivery_status in (None, "delivered") and not row.skipped_in_prompt)


async def _named_turn(db, user_id, key, excluded):
    generation = (await db.execute(select(ChatGeneration.generation_id, ChatGeneration.state)
        .where(ChatGeneration.user_id == user_id, ChatGeneration.round_id == key))).one_or_none()
    rows = list((await db.scalars(select(Log).where(Log.user_id == user_id, Log.round_id == key)
                                  .order_by(Log.sort_seq, Log.id))).all())
    if generation is None:
        # A modern membership without successful round evidence cannot be inferred as legacy.
        linked = await db.scalar(select(ChatGenerationMessage.conversation_id).join(
            Log, Log.id == ChatGenerationMessage.conversation_id).where(
                Log.user_id == user_id, Log.round_id == key, ChatGenerationMessage.user_id == user_id).limit(1))
        if linked is not None or not all(_eligible(row, excluded) for row in rows):
            return None
        return _turn(key, "legacy_round_id", rows)
    if generation.state != "success":
        return None
    included = set(await db.scalars(select(ChatGenerationMessage.conversation_id).where(
        ChatGenerationMessage.user_id == user_id,
        ChatGenerationMessage.generation_id == generation.generation_id,
        ChatGenerationMessage.in_prompt.is_(True))))
    members = [r for r in rows if r.role == "assistant" or r.id in included]
    if (included != {r.id for r in members if r.role == "user"}
            or any(not _eligible(r, excluded) for r in members)):
        return None
    return _turn(key, "modern_success", members)


async def read_completed_history(db, user_id, current_message_ids=(), *, page_size=100):
    if type(page_size) is not int or page_size < 1:
        raise ValueError("invalid_history_page_size")
    excluded = frozenset(current_message_ids)
    newest, seen_keys, fragment = [], set(), []
    discarded = 0
    cursor = None

    def close_fragment():
        nonlocal discarded
        if fragment:
            ordered = list(reversed(fragment))
            turn = _turn(f"legacy:{ordered[0].id}:{ordered[-1].id}", "legacy_inferred", ordered)
            if turn:
                newest.append(turn)
            else:
                discarded += 1
            fragment.clear()

    while len(newest) < ROUND_LIMIT:
        has_link = select(ChatGenerationMessage.conversation_id).where(
            ChatGenerationMessage.conversation_id == Log.id, ChatGenerationMessage.user_id == Log.user_id
        ).exists()
        query = select(Log, or_(ChatMessageState.conversation_id.is_not(None), has_link)).outerjoin(ChatMessageState, and_(
            ChatMessageState.user_id == Log.user_id, ChatMessageState.conversation_id == Log.id)
        ).where(Log.user_id == user_id)
        if cursor is not None:
            seq, message_id = cursor
            query = query.where(or_(Log.sort_seq < seq, and_(Log.sort_seq == seq, Log.id < message_id)))
        page = (await db.execute(query.order_by(Log.sort_seq.desc(), Log.id.desc()).limit(page_size))).all()
        if not page:
            close_fragment()
            break
        for row, modern_member in page:
            if row.round_id is not None:
                close_fragment()
                if len(newest) >= ROUND_LIMIT:
                    break
                if row.round_id not in seen_keys:
                    seen_keys.add(row.round_id)
                    turn = await _named_turn(db, user_id, row.round_id, excluded)
                    if turn:
                        newest.append(turn)
                    else:
                        discarded += 1
            elif modern_member or not _eligible(row, excluded):
                close_fragment()
                discarded += 1
            else:
                if fragment and fragment[-1].role == "user" and row.role == "assistant":
                    close_fragment()
                fragment.append(row)
            if len(newest) >= ROUND_LIMIT:
                break
        last = page[-1][0]
        cursor = last.sort_seq, last.id
    return HistoryCandidates(tuple(reversed(newest[:ROUND_LIMIT])), discarded)
