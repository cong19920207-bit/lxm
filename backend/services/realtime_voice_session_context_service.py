"""STEP-027: bounded, call-owned ephemeral context, never a reply producer.

Only internal, safety-assessed content is accepted. Durable call locks serialize
cache writes with end/deletion fences; Redis Lua serializes append/dedupe/trim.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import select

from backend.models.realtime_voice import VoiceCall, VoiceCallTurn

logger = logging.getLogger(__name__)
TTL_SECONDS = 7200
MAX_ITEMS = 32
MAX_BYTES = 65536
KINDS = frozenset({'turn', 'candidate', 'correction', 'unfinished_topic', 'recalled_topic', 'recall_result'})

_CONTEXT = r'''
if ARGV[2] == 'delete' then redis.call('DEL', KEYS[1]); return {'ok'} end
local raw = redis.call('GET', KEYS[1])
local state = {v=1, user_id=ARGV[1], items={}}
if raw then
  if #raw > tonumber(ARGV[6]) then return {'corrupt'} end
  local ok, decoded = pcall(cjson.decode, raw)
  if not ok or decoded.v ~= 1 or type(decoded.items) ~= 'table' then return {'corrupt'} end
  state = decoded
  if state.user_id ~= ARGV[1] then return {'forbidden'} end
  for key, item in pairs(state.items) do
    if type(key) ~= 'number' or key < 1 or key > #state.items or key ~= math.floor(key) or
       type(item) ~= 'table' or type(item.turn_index) ~= 'number' or
       type(item.visible_from) ~= 'number' or type(item.text) ~= 'string' or
       type(item.kind) ~= 'string' or type(item.id) ~= 'string' or
       (item.delivery_pending ~= nil and type(item.delivery_pending) ~= 'boolean') then return {'corrupt'} end
  end
end
if ARGV[2] == 'read' then return {'ok', cjson.encode(state)} end
local incoming = cjson.decode(ARGV[3])
if ARGV[2] == 'recall_delivered' then
  -- A late worker must not consume a newer result for the same topic.
  -- Keep the facts as a topic cache; this flag means submitted, not adopted.
  for _, item in ipairs(state.items) do
    if item.kind == 'recall_result' then
      for _, sent in ipairs(incoming) do
        if item.id == sent.id and item.turn_index == sent.turn_index and
           item.visible_from == sent.visible_from and item.text == sent.text then
          item.delivery_pending = false
        end
      end
    end
  end
  if raw then
    local encoded = cjson.encode(state)
    if #encoded > tonumber(ARGV[6]) then return {'too_large'} end
    redis.call('SET', KEYS[1], encoded, 'EX', ARGV[4])
  end
  return {'ok'}
end
local items = {}
for _, item in ipairs(state.items) do
  if item.kind ~= incoming.kind or item.id ~= incoming.id then table.insert(items, item) end
end
if ARGV[2] ~= 'remove' then table.insert(items, incoming) end
table.sort(items, function(a,b)
  if a.turn_index == b.turn_index then return a.kind..':'..a.id < b.kind..':'..b.id end
  return a.turn_index < b.turn_index
end)
state.items = items
while #items > tonumber(ARGV[5]) do table.remove(items,1) end
local encoded = cjson.encode(state)
while #encoded > tonumber(ARGV[6]) and #items > 1 do
  table.remove(items,1); encoded = cjson.encode(state)
end
if #encoded > tonumber(ARGV[6]) then return {'too_large'} end
redis.call('SET', KEYS[1], encoded, 'EX', ARGV[4])
return {'ok'}
'''


@dataclass(frozen=True)
class ContextResult:
    status: str
    items: tuple = field(default=(), repr=False)


class VoiceSessionContext:
    def __init__(self, *, cache, session_factory):
        self.cache, self.factory = cache, session_factory

    async def _execute(self, *, call_id, user_id, operation, item=None):
        return await self._bounded(self._perform(call_id=call_id, user_id=user_id, operation=operation, item=item))

    @staticmethod
    async def _bounded(operation):
        try:
            return await asyncio.wait_for(operation, timeout=1)
        except Exception:
            logger.warning('voice.session_context.unavailable')
            return ContextResult('unavailable')

    async def _perform(self, *, call_id, user_id, operation, item=None):
        if not isinstance(call_id, str) or not 1 <= len(call_id) <= 64 or type(user_id) is not int:
            return ContextResult('forbidden')
        try:
            async with self.factory() as db:
                # All access takes the same row lock: no read can expose fenced
                # content and no late worker can resurrect a deleted cache.
                call = await db.scalar(select(VoiceCall).where(VoiceCall.call_id == call_id).with_for_update())
                if call is None or call.user_id != user_id:
                    return ContextResult('forbidden')
                if operation != 'delete' and (call.deletion_fence_at is not None or
                                              call.status not in {'connected', 'reconnecting'}):
                    return ContextResult('closed')
                result = await self.cache.eval(_CONTEXT, 1, f'voice:session_context:{call_id}',
                    str(user_id), operation, json.dumps(item, ensure_ascii=False), TTL_SECONDS, MAX_ITEMS, MAX_BYTES)
                status = result[0].decode() if isinstance(result[0], bytes) else result[0]
                if status != 'ok' or operation != 'read':
                    return ContextResult(status)
                state = json.loads(result[1])
                return ContextResult('ok', tuple(state['items']))
        except Exception:
            logger.warning('voice.session_context.unavailable')
            return ContextResult('unavailable')

    async def append(self, *, call_id, user_id, kind, item_id, turn_index, text, safe, late=False):
        if safe is not True:
            return ContextResult('filtered')
        if (kind not in KINDS or type(turn_index) is not int or turn_index < 1 or
                not isinstance(item_id, str) or not 1 <= len(item_id) <= 128 or
                not isinstance(text, str) or not text.strip()):
            return ContextResult('invalid')
        if len(text.encode('utf-8')) > MAX_BYTES - 1024:
            return ContextResult('too_large')
        item = dict(kind=kind, id=item_id, turn_index=turn_index,
                    visible_from=turn_index + (1 if late else 0), text=text)
        if kind == 'recall_result':
            item['delivery_pending'] = bool(late)
        return await self._execute(call_id=call_id, user_id=user_id, operation='append', item=item)

    async def mark_recall_delivered(self, *, call_id, user_id, items):
        """Atomically mark the exact cached versions submitted through 502."""
        if not isinstance(items, (list, tuple)) or not 1 <= len(items) <= 3:
            return ContextResult('invalid')
        sent = []
        for item in items:
            if (not isinstance(item, dict) or item.get('kind') != 'recall_result'
                    or not isinstance(item.get('id'), str)
                    or not isinstance(item.get('text'), str)
                    or type(item.get('turn_index')) is not int
                    or type(item.get('visible_from')) is not int):
                return ContextResult('invalid')
            sent.append({key: item[key] for key in ('id', 'text', 'turn_index', 'visible_from')})
        return await self._execute(call_id=call_id, user_id=user_id,
                                   operation='recall_delivered', item=sent)

    async def query(self, *, call_id, user_id, turn_index, query=''):
        if type(turn_index) is not int or turn_index < 1 or not isinstance(query, str):
            return ContextResult('invalid')
        result = await self._execute(call_id=call_id, user_id=user_id, operation='read')
        if result.status != 'ok':
            return result
        return ContextResult('ok', tuple(item for item in result.items
            if item['visible_from'] <= turn_index and query.casefold() in item['text'].casefold()))

    async def recalled(self, *, call_id, user_id, turn_index, topic):
        result = await self.query(call_id=call_id, user_id=user_id, turn_index=turn_index)
        return result.status, any(item['kind'] == 'recalled_topic' and item['id'] == topic
                                  for item in result.items)

    async def cleanup(self, *, call_id, user_id):
        return await self._execute(call_id=call_id, user_id=user_id, operation='delete')

    async def remove_candidate(self, *, call_id, user_id, item_id):
        return await self._execute(call_id=call_id, user_id=user_id, operation='remove',
                                   item=dict(kind='candidate', id=item_id))

    async def capture_turn(self, *, call_id, question_id):
        """Fetch committed final/effective facts; never accept generated/interim."""
        return await self._bounded(self._capture_turn(call_id=call_id, question_id=question_id))

    async def _capture_turn(self, *, call_id, question_id):
        async with self.factory() as db:
            pair = (await db.execute(select(VoiceCall.user_id, VoiceCallTurn).join(
                VoiceCallTurn, VoiceCallTurn.call_id == VoiceCall.call_id).where(
                VoiceCall.call_id == call_id, VoiceCallTurn.question_id == question_id))).first()
            if pair is None:
                return ContextResult('missing')
            owner, row = pair
            safe = (row.turn_status in {'finalized', 'interrupted'} and
                    row.user_content_safety_status == row.assistant_content_safety_status == 'passed' and
                    row.user_crisis_status == row.assistant_crisis_status == 'passed' and
                    row.effective_text_evidence != 'none' and row.user_text_final and row.assistant_text_effective)
            if not safe:
                return ContextResult('filtered')
            content = json.dumps(dict(user=row.user_text_final, assistant=row.assistant_text_effective), ensure_ascii=False)
            index = row.turn_index
        return await self.append(call_id=call_id, user_id=owner, kind='turn', item_id=str(index),
                                 turn_index=index, text=content, safe=True)
