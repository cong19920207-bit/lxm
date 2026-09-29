import pytest
from httpx import AsyncClient,ASGITransport
from sqlalchemy import event as sql_event
from backend.models.admin_operation_log import AdminOperationLog
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_turn_service import VoiceTurnService,EffectiveText
from tests.test_realtime_voice_step024_crisis import gate_for,CrisisCache,seed_record,app_for,SENTINEL
from tests.test_realtime_voice_step015_turns import turn_env,storage,event
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
@pytest.mark.parametrize('raw,fail,status,reason',[
    ('["PRIVATE_CRISIS"]',False,'matched',None),(None,False,'suspected','missing'),
    ('[]',False,'suspected','invalid_or_empty'),('bad-json',False,'suspected','invalid_json'),
    ('["safe"]',True,'suspected','redis_unavailable')])
async def test_crisis_classification_and_private_buffer(raw,fail,status,reason):
    gate=gate_for(CrisisCache(raw,fail));sink=CounterCache()
    assert (await gate.assess(call_id='private-call',direction='user',text=SENTINEL)).crisis==status
    events=gate.take_metrics()
    assert ('voice.crisis.assessment',{'direction':'user','result':status},1) in events
    if reason:assert ('voice.crisis.suspected',{'direction':'user','reason':reason},1) in events
    if fail:assert ('voice.crisis.redis_error',{'direction':'user'},1) in events
    assert SENTINEL not in str(events) and 'private-call' not in str(events)
    assert await VoiceMetrics(sink).emit_many(events)


@pytest.mark.asyncio
async def test_committed_hit_and_alert_failure_retry(turn_env):
    factory,call_id=turn_env;sink=CounterCache();gate=gate_for(CrisisCache('["PRIVATE_CRISIS"]'))
    attempts=[]
    async def notify(signal):
        attempts.append(signal)
        if len(attempts)==1:raise ConnectionError('private-notify')
    gate.crisis_gate.notify=notify
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate,metrics=VoiceMetrics(sink))
    await turns.consume(event(call_id,1,'asr_final',SENTINEL))
    await turns.consume(event(call_id,2,'chat_text',SENTINEL,reply='r1'))
    await turns.consume(event(call_id,3,'tts_finished',reply='r1'))
    await turns.apply_effective('r1',EffectiveText(SENTINEL,'full',completed=True))
    events=[e for b in sink.batches for e in b]
    for direction in ('user','assistant'):
        assert events.count(('voice.crisis.hit',{'direction':direction,'result':'matched'},1))==1
    assert ('voice.crisis.alert',{'result':'failure'},1) in events
    assert ('voice.crisis.alert',{'result':'success'},1) in events
    assert len(attempts)==2


@pytest.mark.asyncio
@pytest.mark.parametrize('fail',[False,True])
async def test_audit_result_only_after_attempt(turn_env,fail):
    factory,call_id=turn_env;sink=CounterCache();rid=await seed_record(factory,call_id)
    app=app_for(factory,'super_admin');app.state.voice_metrics=VoiceMetrics(sink)
    def broken(*args):raise RuntimeError('private-audit')
    if fail:sql_event.listen(AdminOperationLog,'before_insert',broken)
    try:
        async with AsyncClient(transport=ASGITransport(app=app,raise_app_exceptions=False),base_url='http://test') as client:
            result=await client.get(f'/api/admin/voice/crisis-records/{rid}')
            assert result.status_code==(500 if fail else 200)
            if fail:assert SENTINEL not in result.text
    finally:
        if fail:sql_event.remove(AdminOperationLog,'before_insert',broken)
    assert sink.batches==[[('voice.crisis.audit',{'action':'detail','result':'failure' if fail else 'success'},1)]]
