"""M4 voice-only safety. No text-channel counters, payloads or playback controls."""
import hashlib
import logging
from collections import Counter
from functools import wraps
from datetime import datetime

from backend.services.content_safety_service import BANNED_KEYWORDS_KEY, match_keyword
from backend.services.realtime_voice_turn_service import GateDecision

logger = logging.getLogger(__name__)

_COUNT_ONCE = """
if redis.call('SET', KEYS[1], '1', 'EX', ARGV[1], 'NX') then
    redis.call('INCR', KEYS[2])
    redis.call('EXPIRE', KEYS[2], ARGV[1])
    return 1
end
return 0
"""


def observe_worker_safety(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        try:
            return await method(self, *args, **kwargs)
        finally:
            gate = getattr(self, 'gate', None) or getattr(self, 'safety_gate', None)
            if gate is not None and hasattr(gate, 'take_metrics'):
                events = gate.take_metrics()
                if events and self.metrics is not None:
                    await self.metrics.emit_many(events)
    return wrapped


class VoiceSafetyGate:
    def __init__(self, *, cache, crisis_gate=None):
        self.cache, self.crisis_gate = cache, crisis_gate
        self._observations = Counter()

    def observe(self, kind, direction, result=None):
        dimensions = {'direction':direction}
        if result is not None:
            dimensions['result'] = result
        key = (kind, tuple(sorted(dimensions.items())))
        self._observations[key] = min(1000000000, self._observations[key] + 1)

    def take_metrics(self):
        observations, self._observations = self._observations, Counter()
        events = [('voice.content_safety.' + name, dict(dimensions), amount)
                for (name, dimensions), amount in observations.items()]
        if self.crisis_gate is not None and hasattr(self.crisis_gate,'take_metrics'):
            events.extend(self.crisis_gate.take_metrics())
        return events

    async def _assess_crisis(self, *, db=None, **kwargs):
        if db is not None and hasattr(self.crisis_gate, 'assess_in_transaction'):
            return await self.crisis_gate.assess_in_transaction(db, **kwargs)
        return await self.crisis_gate.assess(**kwargs)

    async def assess_in_transaction(self, db, **kwargs):
        return await self.assess(db=db, **kwargs)

    async def assess(self, *, call_id, direction, text, db=None):
        try:
            raw = await self.cache.get(BANNED_KEYWORDS_KEY)
            safety = 'matched' if match_keyword(text, raw) is not None else 'passed'
        except Exception:
            safety = 'error_allowed'
        self.observe('result', direction, safety)
        crisis = 'pending'
        keyword = None
        if self.crisis_gate is not None:
            result = await self._assess_crisis(db=db, call_id=call_id, direction=direction, text=text)
            crisis, keyword = result.crisis, result.crisis_keyword
        return GateDecision(safety=safety, crisis=crisis, crisis_keyword=keyword)

    async def record(self, *, call_id, turn_index, direction, decision):
        if decision.safety not in {'passed', 'matched', 'error_allowed'}:
            return
        # Identity contains no keyword, text or content digest.
        identity = hashlib.sha256(f'{call_id}:{turn_index}:{direction}:{decision.safety}'.encode()).hexdigest()
        prefix = 'voice.content_safety.'
        counter = f'{prefix}{decision.safety}:{datetime.utcnow():%Y%m%d}'
        try:
            counted = await self.cache.eval(_COUNT_ONCE, 2, prefix+'seen:'+identity, counter, 172800)
            if not counted:
                self.observe('deduplicated', direction)
            elif decision.safety == 'matched':
                self.observe('keyword_hit', direction)
            elif decision.safety == 'error_allowed':
                self.observe('exception_allowed', direction)
        except Exception:
            self.observe('dedup_unavailable', direction)
            logger.warning('voice.content_safety.metric_unavailable')

    async def isolate(self, db, **kwargs):
        if self.crisis_gate is None:
            raise RuntimeError('voice_crisis_detector_missing')
        return await self.crisis_gate.isolate(db, **kwargs)

    async def after_commit(self, db, *, call_id):
        if self.crisis_gate is not None and hasattr(self.crisis_gate, 'after_commit'):
            await self.crisis_gate.after_commit(db, call_id=call_id)

    async def permits_generated_in_transaction(self, db, **kwargs):
        return await self.permits_generated(db=db, **kwargs)

    async def permits_generated(self, *, call_id, text, db=None):
        # Generated debug text may contain a tail that has not been heard yet.
        # Do not create an effective-text incident for an unplayed tail, but
        # never persist that unassessed tail in the ordinary turn table.
        if self.crisis_gate is None:
            return False
        result = await self._assess_crisis(db=db, call_id=call_id, direction='assistant', text=text)
        return result.crisis == 'passed'
