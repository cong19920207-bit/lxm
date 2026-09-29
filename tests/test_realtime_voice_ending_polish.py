import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from backend.services.realtime_voice_ending_service import ClosingSemanticGate, ClosingOutputBuffer
from tests.test_realtime_voice_step018_ending import policy
from tests.test_realtime_voice_step012_gateway import storage,session
from backend.services.realtime_voice_provider_service import ProviderEvent
from backend.services.realtime_voice_playback_service import PlaybackEvidence

def test_post_playback_delay_is_once_cancellable_and_hard_limit_wins():
    p=policy();p.native_exit('r');p.played('r',now=10)
    assert p.played_deadline==10.8
    p.played('r',now=11);assert p.played_deadline==10.8
    assert p.tick(now=10.79,waiting=False,mic_ok=True,remaining=100)==[]
    assert p.resume(now=11)==['cancel_goodbye']
    assert p.tick(now=12,waiting=False,mic_ok=True,remaining=100)==[]
    p.native_exit('new');p.played('new',now=3599.9)
    assert p.tick(now=3600,waiting=False,mic_ok=True,remaining=100)==['end:hard_limit']

@pytest.mark.asyncio
async def test_gate_distinguishes_denial_from_unavailable():
    async def deny(_):return '{"allowed":false}'
    async def bad(_):return '{"allowed":"true"}'
    assert await ClosingSemanticGate(model=deny).allow_reply('x','y') is False
    assert await ClosingSemanticGate(model=bad).allow_reply('x','y') is None

@pytest.mark.asyncio
async def test_only_exact_bound_fixed_text_bypasses_unavailable_model():
    gate=SimpleNamespace(allow_reply=AsyncMock(return_value=None))
    b=ClosingOutputBuffer(gate)
    def e(kind,payload):return SimpleNamespace(kind=kind,payload=payload,reply_id='r')
    await b.filter(e('chat_text','Goodbye!'),restricted=True,topic='',expected_text='Goodbye.')
    events,rejected=await b.filter(e('text_finished',{}),restricted=True,topic='',expected_text='Goodbye.')
    assert events and not rejected;gate.allow_reply.assert_not_awaited()
    b=ClosingOutputBuffer(gate)
    await b.filter(e('chat_text','Goodbye! Another topic?'),restricted=True,topic='',expected_text='Goodbye.')
    events,rejected=await b.filter(e('text_finished',{}),restricted=True,topic='',expected_text='Goodbye.')
    assert not events and rejected and b.failures['r']=='unavailable'

@pytest.mark.asyncio
async def test_silence_fallback_is_requested_once_and_bound_to_provider_control(storage):
    g=await session(storage);g.connected=True;g.ending=policy()
    g.ending._goodbye('silence_timeout',1)
    g.playback=PlaybackEvidence(call_id=g.call_id,capability_enabled=lambda _:False)
    g.closing_output=ClosingOutputBuffer(SimpleNamespace(allow_reply=AsyncMock(return_value=None)))
    g.adapter.control_query=AsyncMock(return_value=SimpleNamespace(mode='control_requested'))
    async def emit(kind,seq,q='q',r='r',payload=None):
        await g.process_provider_event(ProviderEvent(kind,g.call_id,'s',seq,q,r,payload or {}))
    await emit('chat_text',1,payload='candidate')
    await emit('text_finished',2)
    g.adapter.control_query.assert_awaited_once()
    token=g.adapter.control_query.call_args.kwargs['token']
    await emit('control_confirmed',3,q='fixed',r=None,payload={'control_token':token})
    assert g.fixed_goodbye_questions['fixed']==g.script['silence_and_exit']['silence_timeout_template']
    await emit('sentence_started',4,q='fixed',r='fixedr')
    assert g.ending.goodbye_reply=='fixedr'
    await emit('chat_text',5,q='fixed',r='fixedr',payload=g.script['silence_and_exit']['silence_timeout_template'])
    await emit('tts_audio',6,q='fixed',r='fixedr',payload=b'\0'*4800)
    await emit('text_finished',7,q='fixed',r='fixedr')
    assert g.playback.replies['fixedr'].audio_bytes==4800
    assert g.closing_output.gate.allow_reply.await_count==1

@pytest.mark.asyncio
@pytest.mark.parametrize('reason,decision',[('silence_timeout',False),('time_low',None)])
async def test_fallback_never_bypasses_content_denial_or_time_low(storage,reason,decision):
    g=await session(storage);g.connected=True;g.ending=policy()
    if reason=='silence_timeout':g.ending._goodbye(reason,1)
    else:g.ending.soft_closing=True
    g.closing_output=ClosingOutputBuffer(SimpleNamespace(allow_reply=AsyncMock(return_value=decision)))
    g.adapter.control_query=AsyncMock()
    for seq,kind,data in [(1,'chat_text','candidate'),(2,'text_finished',{})]:
        await g.process_provider_event(ProviderEvent(kind,g.call_id,'s',seq,'q','r',data))
    g.adapter.control_query.assert_not_awaited()
