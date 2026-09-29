"""Voice safety must not change the text-channel wrapper or playback."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from tests.test_realtime_voice_step009_ops import storage
from tests.test_realtime_voice_step015_turns import turn_env, event
from backend.models.realtime_voice import VoiceCallTurn
from backend.services import content_safety_service as content
from backend.services.realtime_voice_turn_service import VoiceTurnService, EffectiveText


class Cache:
    def __init__(self, raw='["blocked"]', fail=False):
        self.raw, self.fail, self.counts, self.seen = raw, fail, {}, set()
    async def get(self, key):
        assert key == 'banned_keywords'
        if self.fail:
            raise RuntimeError('PRIVATE_REDIS_ERROR')
        return self.raw
    async def eval(self, script, count, marker, counter, ttl):
        if self.fail:
            raise RuntimeError('PRIVATE_REDIS_ERROR')
        if marker in self.seen:
            return 0
        self.seen.add(marker)
        self.counts[counter] = self.counts.get(counter, 0) + 1
        return 1


@pytest.mark.asyncio
@pytest.mark.parametrize('raw,text,expected', [('["bad"]','BAD',False), ('bad,other','bad',False), ('["bad"]','ok',True), (None,'bad',True)])
async def test_text_wrapper_retains_legacy_defaults(monkeypatch, raw, text, expected):
    cache = Cache(raw)
    monkeypatch.setattr(content, 'get_redis', AsyncMock(return_value=cache))
    record = AsyncMock()
    monkeypatch.setattr(content, '_record_block', record)
    result = await content.check_content(text)
    await asyncio.sleep(0)
    assert result == {'is_safe': expected, 'reason': '' if expected else '命中违规词: bad'}
    assert record.await_count == (0 if expected else 1)


@pytest.mark.asyncio
async def test_text_wrapper_keeps_fail_open(monkeypatch):
    monkeypatch.setattr(content, 'get_redis', AsyncMock(return_value=Cache(fail=True)))
    assert await content.check_content('test') == {'is_safe': True, 'reason': ''}


@pytest.mark.asyncio
@pytest.mark.parametrize('raw,fail,status', [('["blocked"]',False,'matched'), ('["other"]',False,'passed'), ('invalid-json',False,'error_allowed'), ('{}',False,'error_allowed'), ('[]',True,'error_allowed')])
async def test_voice_detector_distinguishes_errors_without_shared_logs(raw, fail, status, caplog):
    from backend.services.realtime_voice_safety_service import VoiceSafetyGate
    cache = Cache(raw, fail)
    gate = VoiceSafetyGate(cache=cache)
    decision = await gate.assess(call_id='call', direction='user', text='blocked PRIVATE_SENTINEL')
    assert decision.safety == status
    assert decision.crisis == 'pending'
    assert cache.counts == {}
    assert 'PRIVATE' not in caplog.text and 'blocked' not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize('raw,status', [('["blocked"]','matched'), ('not-json','error_allowed')])
async def test_both_directions_skip_memory_and_metrics_are_idempotent(turn_env, raw, status, caplog):
    from backend.services.realtime_voice_safety_service import VoiceSafetyGate
    from backend.services.realtime_voice_turn_service import GateDecision
    class PassedCrisis:
        async def assess(self, **kwargs):
            return GateDecision(crisis='passed')
    factory, call_id = turn_env
    cache = Cache(raw)
    gate = VoiceSafetyGate(cache=cache, crisis_gate=PassedCrisis())
    turns = VoiceTurnService(call_id=call_id, session_id='session1', session_factory=factory, gate=gate)
    await turns.consume(event(call_id,1,'asr_final','blocked PRIVATE_SENTINEL'))
    await turns.consume(event(call_id,2,'chat_text','blocked reply',reply='r1'))
    await turns.apply_effective('r1', EffectiveText('blocked', 'confirmed_sentences'))
    await turns.consume(event(call_id,3,'tts_finished',reply='r1'))
    await turns.apply_effective('r1', EffectiveText('blocked reply','full',completed=True))
    async with factory() as db:
        row = await db.scalar(select(VoiceCallTurn))
        assert row.user_content_safety_status == row.assistant_content_safety_status == status
        assert row.memory_status == 'skipped'
        assert row.turn_status == 'finalized' and row.effective_text_evidence == 'full'
    assert sum(cache.counts.values()) == 2
    assert all(k.startswith('voice.content_safety.') for k in cache.counts)
    assert 'PRIVATE' not in caplog.text


@pytest.mark.asyncio
async def test_matched_partial_cannot_be_reclassified_by_keyword_reload(turn_env):
    from backend.services.realtime_voice_safety_service import VoiceSafetyGate
    from backend.services.realtime_voice_turn_service import GateDecision
    class PassedCrisis:
        async def assess(self, **kwargs):return GateDecision(crisis='passed')
    factory,call_id=turn_env
    cache=Cache('["blocked"]')
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=VoiceSafetyGate(cache=cache,crisis_gate=PassedCrisis()))
    await turns.consume(event(call_id,1,'asr_final','hello'))
    await turns.consume(event(call_id,2,'chat_text','blocked reply',reply='r1'))
    await turns.apply_effective('r1',EffectiveText('blocked','confirmed_sentences'))
    cache.raw='[]'
    await turns.consume(event(call_id,3,'tts_finished',reply='r1'))
    await turns.apply_effective('r1',EffectiveText('blocked reply','full',completed=True))
    async with factory() as db:
        row=await db.scalar(select(VoiceCallTurn))
        assert row.assistant_content_safety_status=='matched' and row.memory_status=='skipped'
