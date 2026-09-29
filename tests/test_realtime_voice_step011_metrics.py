import pytest
from backend.services.realtime_voice_decision_service import decide_call
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step031_metrics import CounterCache
from tests.test_realtime_voice_step012_gateway import storage,test_real_lifecycle_result_meter_replay_and_scoped_metrics as check_lifecycle


@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['valid','invalid','timeout'])
async def test_decision_output_and_fallback_closed_metrics(monkeypatch,mode):
    from types import SimpleNamespace
    import backend.services.realtime_voice_decision_service as module
    ticks=iter((1.0,2.0));monkeypatch.setattr(module,"clock",SimpleNamespace(monotonic=lambda:next(ticks)))
    sink=CounterCache()
    async def model(prompt):
        if mode=='timeout':raise TimeoutError('private-provider')
        return 'private-invalid' if mode=='invalid' else '{"answer":true,"delay_seconds":4,"opening_text":"private-opening"}'
    await decide_call(inputs={'private':'private-input'},settings={'prompt_template':'private-template'},model=model,metrics=VoiceMetrics(sink))
    events=[e for b in sink.batches for e in b]
    assert ('voice.call01.output',{'result':mode},1) in events
    assert ('voice.call01.decision_duration_ms',{'result':'model' if mode=='valid' else 'fallback'},1000) in events
    if mode!='valid':assert ('voice.call01.fallback',{'reason':'timeout' if mode=='timeout' else 'decision_invalid'},1) in events
    assert 'private-' not in str(events)


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome',['connected','missed','cancelled','failed','cancelled_deciding'])
async def test_actual_lifecycle_metrics_not_replayed(storage,monkeypatch,caplog,outcome):
    import backend.services.realtime_voice_gateway_service as module
    sink=CounterCache();original=module.VoiceGatewaySession.__init__
    def init(self,*args,**kwargs):
        original(self,*args,**kwargs);self.metrics=VoiceMetrics(sink)
    monkeypatch.setattr(module.VoiceGatewaySession,'__init__',init)
    await check_lifecycle(storage,monkeypatch,caplog,True,outcome)
    events=[e for b in sink.batches for e in b]
    expected='cancelled' if outcome=='cancelled_deciding' else outcome
    assert events.count(('voice.call01.ringing_result',{'result':expected},1))==1
    assert sum(e[0]=='voice.call01.provider_ready' for e in events)==1
    # A rejected repeat lifecycle may run a decision, but cannot invent another ringing result.
    assert all('sentinel' not in str(e) for e in events)


@pytest.mark.asyncio
@pytest.mark.parametrize('answer',[False,True])
async def test_committed_result_survives_browser_state_send_failure(storage,monkeypatch,answer):
    import json
    from types import SimpleNamespace
    from sqlalchemy import select
    from backend.models.realtime_voice import VoiceCall
    from tests.test_realtime_voice_step012_gateway import session
    import backend.services.realtime_voice_gateway_service as module
    gateway=await session(storage);sink=CounterCache();gateway.metrics=VoiceMetrics(sink);clock=[0.0]
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    async def inputs(*args,**kwargs):return {}
    async def model(prompt):return json.dumps({'answer':answer,'delay_seconds':6,'opening_text':''})
    async def warmup():clock[0]=6.0;return 3.0
    expected='connected' if answer else 'missed'
    original_send=gateway.send
    async def send(kind,**kwargs):
        if kwargs.get('status')==expected:raise ConnectionError('browser gone')
        await original_send(kind,**kwargs)
    monkeypatch.setattr(module,'call_decision_inputs',inputs)
    gateway.script['call_answer']['prompt_template']='synthetic';gateway.decision_model=model
    gateway.warmup=warmup;gateway.send=send
    with pytest.raises(ConnectionError):await gateway.lifecycle()
    async with storage() as db:assert (await db.scalar(select(VoiceCall))).status==expected
    assert [e for b in sink.batches for e in b if e[0]=='voice.call01.ringing_result']==[
        ('voice.call01.ringing_result',{'result':expected},1)]
