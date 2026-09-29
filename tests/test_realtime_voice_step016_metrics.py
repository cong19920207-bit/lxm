import pytest
from types import SimpleNamespace
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_playback_service import observe_playback
from tests.test_realtime_voice_step016_playback import reply,client
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
@pytest.mark.parametrize('mapping,sentences,kind,expected',[
    (True,False,'client_barge_in','exact_played'),
    (False,True,'client_barge_in','confirmed_sentences'),
    (False,False,'client_barge_in','none'),
    (False,False,'client_reply_playback_completed','full')])
async def test_evidence_counter_and_drain(mapping,sentences,kind,expected):
    engine,first,_=reply(mapping,sentences);sink=CounterCache()
    engine.client(client('client_sentence_played',1,sentence_id=first))
    engine.take_metrics()
    engine.client(client(kind,2,**({'played_audio_ms':100} if kind=='client_barge_in' else {})))
    events=engine.take_metrics()
    assert ('voice.effective_text.evidence',{'level':expected},1) in events
    await VoiceMetrics(sink).emit_many(events)
    assert sink.batches==[events] and engine.take_metrics()==[]
    assert '第一句' not in str(events) and 'call1' not in str(events)


@pytest.mark.asyncio
async def test_invalid_duplicate_out_of_order_and_finally_delivery():
    engine,_,_=reply();sink=CounterCache();owner=SimpleNamespace(playback=engine,metrics=VoiceMetrics(sink),advanced=False)
    engine.client(client('client_playback_progress',2,played_audio_ms=0))
    engine.client(client('client_playback_progress',2,played_audio_ms=0))
    engine.client(client('client_playback_progress',1,played_audio_ms=0))
    @observe_playback
    async def operation(self):
        self.advanced=True
        self.playback=reply()[0] # old object's events still delivered
        with pytest.raises(ValueError):engine.client(client('client_audio_playback_completed',3,played_audio_ms=199))
        raise RuntimeError('existing business failure')
    with pytest.raises(RuntimeError):await operation(owner)
    assert owner.advanced
    events=[e for b in sink.batches for e in b]
    for kind in ('invalid_client_event','duplicate_client_event','out_of_order_client_event','mapping_unavailable','ack_unavailable'):
        assert ('voice.effective_text.event',{'kind':kind},1) in events

from tests.test_realtime_voice_step012_gateway import storage

@pytest.mark.asyncio
async def test_rebuilt_production_adapter_retains_metric_sink(storage,monkeypatch):
    import tests.test_realtime_voice_step019_reconnect as scenario
    from backend.services.realtime_voice_provider_service import VoiceProviderAdapter
    class MetricsAdapter(scenario.RebuildAdapter,VoiceProviderAdapter):
        async def create_connection(self):
            assert self.metrics is not None
            await super().create_connection()
    monkeypatch.setattr(scenario,'RebuildAdapter',MetricsAdapter)
    await scenario.test_gateway_new_session_uses_formal_pack_and_exact_bridge_same_call(storage)


@pytest.mark.asyncio
@pytest.mark.parametrize('mapping,sentences,kind,level,evidence',[
    (True,False,'client_barge_in','exact_played','verified'),
    (False,True,'client_barge_in','confirmed_sentences','verified'),
    (False,False,'client_barge_in','none','unverified'),
    (False,False,'client_reply_playback_completed','full','unverified'),
    (True,False,'client_reply_playback_completed','full','verified')])
async def test_effective_samples_include_capability_at_snapshot(mapping,sentences,kind,level,evidence):
    engine,first,_=reply(mapping,sentences)
    engine.client(client('client_sentence_played',1,sentence_id=first));engine.take_metrics()
    engine.client(client(kind,2,**({'played_audio_ms':100} if kind=='client_barge_in' else {})))
    events=engine.take_metrics()
    assert ('voice.effective_text.observed',{'level':level,'evidence':evidence},1) in events
    assert engine.take_metrics()==[]
