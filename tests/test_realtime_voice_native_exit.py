from unittest.mock import AsyncMock
import pytest
from backend.services.realtime_voice_provider_service import ProviderEvent
from backend.services.realtime_voice_playback_service import PlaybackEvidence
from tests.test_realtime_voice_step018_ending import policy
from tests.test_realtime_voice_step012_gateway import storage, session
from tests.test_realtime_voice_step007_provider import connected, response, api

@pytest.mark.asyncio
async def test_adapter_enables_native_exit_and_preserves_bound_status(monkeypatch):
    a, wire = await connected(monkeypatch)
    import gzip,json
    start=next(x for x in wire.sent if int.from_bytes(x[4:8],'big')==100)
    n=int.from_bytes(start[8:12],'big'); offset=12+n
    payload=json.loads(gzip.decompress(start[offset+4:]))
    assert payload['dialog']['extra']['enable_user_query_exit'] is True
    def event(kind, body): return a._normalize(api().decode_frame(response(kind,a.session_id,body)))
    event(450,{'question_id':'q'})
    event(350,{'question_id':'q','reply_id':'r'})
    done=event(359,{'question_id':'q','reply_id':'r','status_code':'20000002'})
    assert done.payload['status_code']=='20000002'
    assert event(359,{'question_id':'q','reply_id':'r','status_code':'20000002'}) is None
    event(450,{'question_id':'new'})
    assert event(359,{'question_id':'q','reply_id':'late','status_code':'20000002'}) is None

def test_native_exit_waits_for_playback_without_second_goodbye_or_timeout():
    p=policy()
    assert p.native_exit('r')==[]
    assert p.pending_reason=='exit_intent'
    assert p.tick(now=100,waiting=False,mic_ok=True,remaining=100)==[]
    assert p.played('other')==[]
    assert p.resume(now=101)==['cancel_goodbye']
    assert p.played('r')==[]
    p.native_exit('new')
    assert p.played('new',now=5)==[]
    assert p.tick(now=6.2,waiting=False,mic_ok=True,remaining=100)==['end:exit_intent']

@pytest.mark.asyncio
async def test_gateway_native_exit_no_classifier_cancellable_and_actual_playback(storage):
    g=await session(storage);g.connected=True;g.ending=policy()
    g.semantic_gate.explicit_exit=AsyncMock(side_effect=AssertionError('text exit classifier called'))
    g.playback=PlaybackEvidence(call_id=g.call_id,capability_enabled=lambda _:False)
    g.turns=None
    g.request_end=AsyncMock()
    import time
    g.ending.connected_at=time.monotonic()
    seq=0
    async def emit(kind,q='q',r=None,payload=None):
        nonlocal seq
        seq+=1
        await g.process_provider_event(ProviderEvent(kind,g.call_id,'s',seq,q,r,payload or {}))
    await emit('user_speech_started')
    await emit('asr_final',payload='bye')
    await emit('tts_audio',r='r',payload=b'\0'*4800)
    await emit('tts_finished',r='r',payload={'status_code':'20000002'})
    assert g.ending.goodbye_reply=='r'
    assert g.socket.frames[-1]['metadata']['kind']=='tts_finished'
    g.request_end.assert_not_awaited()
    await emit('user_speech_started',q='q2')
    assert g.ending.pending_reason is None
    assert g.ending.played('r')==[]
    await emit('tts_audio',q='q2',r='r2',payload=b'\0'*4800)
    await emit('tts_finished',q='q2',r='r2',payload={'status_code':'20000002'})
    g.turns=type('Turns',(),{'apply_effective':AsyncMock()})()
    await g.handle_playback({'type':'client_audio_playback_completed','call_id':g.call_id,
                           'reply_id':'r2','event_seq':1,'played_audio_ms':100})
    g.request_end.assert_not_awaited()
    await g.handle_end_actions(g.ending.tick(now=g.ending.played_deadline,waiting=False,mic_ok=True,remaining=100))
    g.request_end.assert_awaited_once_with(reason='exit_intent')
    g.semantic_gate.explicit_exit.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize('status', [None,20000002,'other'])
async def test_gateway_ignores_non_native_status(storage,status):
    g=await session(storage);g.ending=policy()
    await g.observe_ending_event(ProviderEvent('tts_finished',g.call_id,'s',1,'q','r',{'status_code':status}))
    assert g.ending.pending_reason is None

@pytest.mark.asyncio
@pytest.mark.parametrize('mismatch', ['session','question','no_audio','interrupted'])
async def test_native_exit_rejects_unbound_or_stopped_reply(storage,mismatch):
    g=await session(storage);g.ending=policy();g.native_question=('s','q')
    g.playback=PlaybackEvidence(call_id=g.call_id,capability_enabled=lambda _:False)
    g.playback.feed(ProviderEvent('tts_audio',g.call_id,'s',1,'q','r',b'\0'*4800))
    if mismatch=='no_audio':g.playback.replies['r'].audio_bytes=0
    if mismatch=='interrupted':g.playback.replies['r'].interrupted=True
    await g.observe_ending_event(ProviderEvent('tts_finished',g.call_id,
        'other' if mismatch=='session' else 's',2,
        'other' if mismatch=='question' else 'q','r',{'status_code':'20000002'}))
    assert g.ending.pending_reason is None

def test_native_exit_keeps_hard_limit_and_silence_ownership():
    p=policy();p.native_exit('r')
    assert p.tick(now=3600,waiting=False,mic_ok=True,remaining=100)==['end:hard_limit']
    p=policy();p._goodbye('silence_timeout',1);p.bind_goodbye('silence',p.generation)
    p.native_exit('r')
    assert p.goodbye_reply=='silence' and p.pending_reason=='silence_timeout'

@pytest.mark.asyncio
async def test_disconnect_invalidates_native_exit_before_async_rebuild(storage):
    g=await session(storage);g.ending=policy();g.ending.native_exit('old')
    g.native_question=('s','q');g.observe=AsyncMock(side_effect=RuntimeError('stop before DB'))
    with pytest.raises(RuntimeError):await g.disconnected(True)
    assert g.native_question is None and g.ending.played('old')==[]
