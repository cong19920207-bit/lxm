"""Voice crisis isolation and metadata-only alerts. No role-model injection."""
import asyncio
import logging
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select, update

from backend.models.realtime_voice import VoiceCrisisRecord
from backend.services.realtime_voice_turn_service import GateDecision

logger = logging.getLogger(__name__)


class VoiceCrisisGate:
    def __init__(self, *, loader, notify=None):
        self.loader, self.notify = loader, notify
        self._observations = Counter()
        self._notified = False
        self._notify_lock = asyncio.Lock()

    def observe(self, name, **dimensions):
        key = (name, tuple(sorted(dimensions.items())))
        self._observations[key] = min(1000000000, self._observations[key] + 1)

    def take_metrics(self):
        observations, self._observations = self._observations, Counter()
        return [('voice.crisis.' + name, dict(dimensions), amount)
                for (name, dimensions), amount in observations.items()]

    async def assess_in_transaction(self, db, **kwargs):
        return await self.assess(db=db, **kwargs)

    async def assess(self, *, call_id, direction, text, db=None):
        try:
            loaded = await self.loader.load_crisis_keywords(**({'db': db} if db is not None else {}))
            if loaded.suspected_hit:
                reason = loaded.failure_reason
                reason = reason if reason in {'redis_unavailable','missing','invalid_json','invalid_or_empty'} else 'unavailable'
                self.observe('suspected', direction=direction, reason=reason)
                if reason == 'redis_unavailable':
                    self.observe('redis_error', direction=direction)
                result = GateDecision(crisis='suspected')
            else:
                keyword = next((word for word in loaded.keywords if word.lower() in text.lower()), None)
                result = GateDecision(crisis='matched' if keyword else 'passed', crisis_keyword=keyword)
        except Exception:
            logger.error('voice.crisis.detector_unavailable')
            self.observe('suspected', direction=direction, reason='unavailable')
            result = GateDecision(crisis='suspected')
        self.observe('assessment', direction=direction, result=result.crisis)
        return result

    async def isolate(self, db, *, call, turn, direction, text, decision):
        existing = await db.scalar(select(VoiceCrisisRecord).where(
            VoiceCrisisRecord.call_id == call.call_id,
            VoiceCrisisRecord.turn_index == turn.turn_index,
            VoiceCrisisRecord.direction == direction))
        if existing is not None:
            # Playback evidence is cumulative. Never shorten the record on an
            # old ACK, refresh retention, or alert again for the same side.
            if (existing.cleared_at is None and existing.expires_at > datetime.utcnow()
                    and (decision.effective_final or text.startswith(existing.content_plaintext or ''))):
                existing.content_plaintext = text
                await db.flush()
            return
        db.add(VoiceCrisisRecord(call_id=call.call_id, turn_index=turn.turn_index,
            direction=direction, content_plaintext=text, matched_keyword=decision.crisis_keyword,
            match_status=decision.crisis, is_persona_incident=direction == 'assistant',
            expires_at=datetime.utcnow()+timedelta(days=30)))
        await db.flush()
        from backend.services.realtime_voice_metric_service import stage_voice_metrics
        stage_voice_metrics(db,[('voice.crisis.hit',{'direction':direction,'result':decision.crisis},1)])
        # Alert contains identity/status only, including on suspected matches.
        log = logger.critical if direction == 'assistant' else logger.error
        log('voice.crisis.%s call_id=%s turn_index=%s status=%s',
            'persona_incident' if direction == 'assistant' else 'detected',
            call.call_id, turn.turn_index, decision.crisis)

    async def after_commit(self, db, *, call_id):
        async with self._notify_lock:
            await self._notify_after_commit(db, call_id=call_id)

    async def _notify_after_commit(self, db, *, call_id):
        if self._notified or self.notify is None:
            return
        found = await db.scalar(select(VoiceCrisisRecord.id).where(
            VoiceCrisisRecord.call_id == call_id, VoiceCrisisRecord.cleared_at.is_(None),
            VoiceCrisisRecord.expires_at > datetime.utcnow()).limit(1))
        if found is not None:
            try:
                await self.notify({'type': 'crisis_detected', 'call_id': call_id})
            except BaseException:
                self.observe('alert', result='failure')
                raise
            self._notified = True
            self.observe('alert', result='success')


async def clear_expired_crisis(db, *, now=None):
    now = now or datetime.utcnow()
    result = await db.execute(update(VoiceCrisisRecord).where(
        VoiceCrisisRecord.expires_at <= now, VoiceCrisisRecord.cleared_at.is_(None)
    ).values(content_plaintext=None, matched_keyword=None, cleared_at=now))
    return result.rowcount
