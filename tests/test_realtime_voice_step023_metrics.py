import pytest
from backend.services.realtime_voice_safety_service import VoiceSafetyGate
from backend.services.realtime_voice_turn_service import VoiceTurnService
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step023_safety import Cache
from tests.test_realtime_voice_step015_turns import storage,turn_env,event
from tests.test_realtime_voice_step031_metrics import CounterCache


@pytest.mark.asyncio
@pytest.mark.parametrize('raw,status',[('["blocked"]','matched'),('[]','passed'),('not-json','error_allowed')])
async def test_direction_result_and_idempotent_detection(raw,status):
    gate=VoiceSafetyGate(cache=Cache(raw));sink=CounterCache()
    for direction in ('user','assistant'):
        d=await gate.assess(call_id='private-call',direction=direction,text='blocked private-text')
        for _ in range(2):await gate.record(call_id='private-call',turn_index=1,direction=direction,decision=d)
    events=gate.take_metrics()
    for direction in ('user','assistant'):
        assert ('voice.content_safety.result',{'direction':direction,'result':status},1) in events
        assert ('voice.content_safety.deduplicated',{'direction':direction},1) in events
        if status!='passed':
            assert ('voice.content_safety.'+('keyword_hit' if status=='matched' else 'exception_allowed'),{'direction':direction},1) in events
    assert 'private' not in str(events) and gate.take_metrics()==[]
    assert await VoiceMetrics(sink).emit_many(events)


@pytest.mark.asyncio
async def test_gate_metrics_flow_after_turn_lock(turn_env):
    factory,call_id=turn_env;sink=CounterCache();gate=VoiceSafetyGate(cache=Cache(fail=True))
    turns=VoiceTurnService(call_id=call_id,session_id='session1',session_factory=factory,gate=gate)
    class Metrics:
        async def emit_many(self,events):
            assert not turns._lock.locked()
            await VoiceMetrics(sink).emit_many(events)
    turns.metrics=Metrics()
    await turns.consume(event(call_id,1,'asr_final','private'))
    events=[e for b in sink.batches for e in b]
    assert ('voice.content_safety.result',{'direction':'user','result':'error_allowed'},1) in events
    assert ('voice.content_safety.dedup_unavailable',{'direction':'user'},1) in events

from tests.test_realtime_voice_step031_jobs import summary_env,card_env,memory_env,service
from tests.test_realtime_voice_step028_jobs import add_turn,Writer,Gate

@pytest.mark.asyncio
async def test_memory_worker_drains_safe_gate_after_job(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    factory,call_id=memory_env;turn=await add_turn(factory,call_id);sink=CounterCache()
    gate=VoiceSafetyGate(cache=Cache('[]'),crisis_gate=Gate())
    async def model(_):return '{"memory_items":[]}'
    worker=VoiceMemoryService(session_factory=factory,gate=gate,model=model,writer=Writer(),metrics=VoiceMetrics(sink))
    await worker.enqueue(call_id=call_id,turn_id=turn)
    await worker.process_next(call_id=call_id)
    assert any(e[0]=='voice.content_safety.result' for b in sink.batches for e in b)
    assert gate.take_metrics()==[]


@pytest.mark.asyncio
async def test_summary_worker_drains_assistant_gate_after_result(summary_env):
    factory,call_id=summary_env;sink=CounterCache();gate=VoiceSafetyGate(cache=Cache('[]'),crisis_gate=Gate())
    worker=service(factory);worker.safety_gate=gate;worker.metrics=VoiceMetrics(sink)
    async def permits(**kw):
        result=await gate.assess(direction='assistant',**kw)
        return result.safety==result.crisis=='passed'
    worker.permits=permits
    await worker.enqueue(call_id=call_id)
    assert await worker.process(call_id=call_id)=='ready'
    assert any(e[0]=='voice.content_safety.result' and e[1]['direction']=='assistant' for b in sink.batches for e in b)
    assert gate.take_metrics()==[]
