import json
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall,VoiceCallTurn
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from tests.test_realtime_voice_step028_jobs import storage,memory_env,add_turn,Gate,Writer
from tests.test_realtime_voice_step031_metrics import CounterCache


def atoms():
    valid=[dict(memory_type='user',stable_key=f'旅行-计划-地点{i}',content=f'计划去地点{i}') for i in range(6)]
    return [valid[0],valid[0],None,*valid[1:]]


@pytest.mark.asyncio
async def test_extract_buckets_drops_and_idempotent_enqueue(memory_env):
    factory,call_id=memory_env;sink=CounterCache();writer=Writer()
    async def model(_):return json.dumps({'memory_items':atoms()})
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=writer,metrics=VoiceMetrics(sink))
    turn=await add_turn(factory,call_id)
    await svc.enqueue(call_id=call_id,turn_id=turn);await svc.enqueue(call_id=call_id,turn_id=turn)
    assert await svc.process_next(call_id=call_id)=='success'
    events=[e for b in sink.batches for e in b]
    assert events.count(('voice.memory_extract.enqueue',{'result':'pending'},1))==1
    assert ('voice.memory_extract.output',{'bucket':'5'},1) in events
    for reason in ('duplicate_key','invalid_atom','item_limit'):
        assert ('voice.memory_extract.drop',{'reason':reason},1) in events
    assert events.count(('voice.memory_upsert.result',{'result':'written'},1))==5
    assert all('旅行' not in str(e) and call_id not in str(e) for e in events)


@pytest.mark.asyncio
async def test_skip_admission_and_transaction_rollback(memory_env):
    factory,call_id=memory_env;sink=CounterCache();metrics=VoiceMetrics(sink)
    turn_id=await add_turn(factory,call_id,user_asr_confidence=.49)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));turn=await db.get(VoiceCallTurn,turn_id)
        assert await VoiceMemoryService.stage_job(db,call=call,turn=turn)=='skipped'
        await db.rollback();await flush_voice_metrics(db,metrics)
    assert not sink.batches
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),metrics=metrics)
    await svc.enqueue(call_id=call_id,turn_id=turn_id)
    assert ('voice.memory_extract.skip',{'reason':'low_confidence'},1) in [e for b in sink.batches for e in b]


@pytest.mark.asyncio
@pytest.mark.parametrize('raw,result,reason',[
    ('broken','skipped','invalid_output'),('{"memory_items":[]}','skipped','no_items')])
async def test_invalid_and_empty_output_have_explicit_skip(memory_env,raw,result,reason):
    factory,call_id=memory_env;sink=CounterCache()
    async def model(_):return raw
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,metrics=VoiceMetrics(sink))
    await svc.enqueue(call_id=call_id,turn_id=await add_turn(factory,call_id))
    assert await svc.process_next(call_id=call_id)==result
    assert ('voice.memory_extract.skip',{'reason':reason},1) in [e for b in sink.batches for e in b]
