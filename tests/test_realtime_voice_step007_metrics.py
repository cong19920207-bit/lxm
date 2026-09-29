import json
from uuid import uuid4
import pytest
from backend.constants.realtime_voice_config import VOICE_CAPABILITY_KEYS
from backend.services.realtime_voice_provider_service import VoiceProviderAdapter,ProviderError
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step007_provider import Wire,config,response
from tests.test_realtime_voice_step031_metrics import CounterCache


async def start(monkeypatch,metrics):
    monkeypatch.setenv('DOUBAO_S2S_APP_ID','test-app')
    wire=Wire()
    async def connect(*args,**kwargs):return wire
    adapter=VoiceProviderAdapter(call_id=str(uuid4()),config=config(),transport_factory=connect,metrics=metrics)
    await adapter.inject_context('private-persona','private-context')
    await adapter.create_connection(secret='private-secret');await adapter.start_session()
    await adapter.receive_event()  # session_ready
    return adapter,wire


@pytest.mark.asyncio
@pytest.mark.parametrize('usage',['received','invalid','missing','late'])
async def test_provider_usage_and_session_observation(monkeypatch,usage):
    sink=CounterCache();adapter,wire=await start(monkeypatch,VoiceMetrics(sink))
    if usage=='late':
        await wire.incoming.put(response(152,adapter.session_id));assert (await adapter.receive_event()).kind=='session_finished'
    if usage!='missing':
        data={'input_tokens':4,'output_tokens':2} if usage!='invalid' else {'input_tokens':'private-invalid'}
        await wire.incoming.put(response(154,adapter.session_id,data))
        assert (await adapter.receive_event()).kind=='usage'
    await adapter.finish_session();before=list(sink.batches);await adapter.finish_session();assert before==sink.batches
    events=[e for batch in sink.batches for e in batch]
    assert ('voice.provider.session',{'operation':'connect','result':'success'},1) in events
    assert ('voice.provider.start',{'result':'success'},1) in events
    assert {e[1]['capability'] for e in events if e[0]=='voice.provider.capability'}==set(VOICE_CAPABILITY_KEYS)
    assert all(e[1]['result']=='not_measurable' for e in events if e[0]=='voice.provider.capability')
    assert ('voice.provider.usage',{'result':usage},1) in events
    assert events.count(('voice.provider.usage',{'result':'missing'},1))==(usage in {'missing','invalid','late'})
    assert 'private-' not in json.dumps(events) and adapter.call_id not in json.dumps(events)


@pytest.mark.asyncio
async def test_provider_error_and_disabled_capability_fallback(monkeypatch):
    sink=CounterCache();adapter,wire=await start(monkeypatch,VoiceMetrics(sink))
    adapter._reply='known';adapter._question='known-question'
    assert (await adapter.interrupt_reply('known')).mode=='local_stop_only'
    assert (await adapter.truncate_reply_context('known',0)).mode=='context_not_truncated'
    assert (await adapter.inject_rag('known-question','private-rag')).mode=='next_turn'
    await wire.incoming.put(b'bad-frame')
    with pytest.raises(ProviderError):await adapter.receive_event()
    await adapter.finish_session()
    events=[e for batch in sink.batches for e in batch]
    assert ('voice.provider.error',{'reason':'protocol_error'},1) in events
    assert {e[1]['capability'] for e in events if e[0]=='voice.provider.capability' and e[1]['result']=='downgraded'}=={
        'supports_reply_cancel','supports_context_truncate','supports_current_turn_rag_gate'}


@pytest.mark.asyncio
async def test_provider_initial_failure_and_metric_outage_preserve_behavior(monkeypatch):
    sink=CounterCache();adapter=VoiceProviderAdapter(call_id='private-call',config=config(),metrics=VoiceMetrics(sink))
    monkeypatch.delenv('DOUBAO_S2S_APP_ID',raising=False)
    with pytest.raises(ProviderError,match='credential_missing'):await adapter.create_connection(secret='private-secret')
    assert ('voice.provider.error',{'reason':'credential_missing'},1) in [e for b in sink.batches for e in b]
    class Broken:
        async def eval(self,*args):raise ConnectionError('private-redis-secret')
    adapter,wire=await start(monkeypatch,VoiceMetrics(Broken()))
    assert adapter._ready
    await adapter.finish_session()


@pytest.mark.asyncio
async def test_same_session_reconnect_preserves_usage_observation(monkeypatch):
    from tests.test_realtime_voice_step007_provider import verified_capability
    sink=CounterCache();adapter,wire=await start(monkeypatch,VoiceMetrics(sink))
    adapter._capabilities['supports_session_reconnect']=verified_capability()
    await wire.incoming.put(response(154,adapter.session_id,{'input_tokens':3}))
    await adapter.receive_event()
    session_id=adapter.session_id
    assert (await adapter.reconnect_session()).mode=='same_dialog'
    assert adapter.session_id==session_id
    await adapter.finish_session()
    assert ('voice.provider.usage',{'result':'missing'},1) not in [e for b in sink.batches for e in b]
