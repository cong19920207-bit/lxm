"""Actual Redis frequency storage, atomic rejection, TTL and read projection."""
import os,json
from datetime import datetime,timezone
import pytest
from tests.test_realtime_voice_m4_runtime import containers,runtime
from backend.services.realtime_voice_metric_service import VoiceMetrics,DURATION_PREFIX
from backend.services.realtime_voice_metric_read_service import read_duration_day
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores opt-in')


@pytest.mark.asyncio
async def test_actual_redis_histograms_atomicity_and_read(runtime):
    cache=runtime[2];day=datetime.now(timezone.utc).date()
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    sink=VoiceMetrics(cache,deadline_seconds=1)
    assert await sink.emit_many([('voice.call01.decision_duration_ms',{'result':'model'},v) for v in (0,50,50,100)])
    result=await read_duration_day(cache,day)
    row=next(row for row in result['events'] if row['name']=='voice.call01.decision_duration_ms')
    assert row['groups']==[{'dimensions':{'result':'model'},'sample_count':4,'method':'nearest_rank',
        'status':'available','p50_ms':50,'p90_ms':100,'p95_ms':100}]
    key=DURATION_PREFIX+'voice.call01.decision_duration_ms:'+day.strftime('%Y%m%d')
    assert 172790<=await cache.ttl(key)<=172800
    ordinary='voice.call01.decision_duration_ms:'+day.strftime('%Y%m%d')
    assert await cache.hgetall(ordinary)=={'{"result":"model"}':'200'}
    # Wrong histogram type must reject the whole batch before changing the sum.
    await cache.delete(key);await cache.set(key,'corrupt')
    assert not await sink.emit_many([('voice.call01.decision_duration_ms',{'result':'model'},100)])
    assert await cache.hgetall(ordinary)=={'{"result":"model"}':'200'}
    assert {key:await cache.get(key) for key in shared}==shared

    await cache.delete(key)
    for malformed in ('01','00'):
        await cache.hset(ordinary, '{"result":"model"}', malformed)
        assert not await sink.emit_many([('voice.call01.decision_duration_ms',{'result':'model'},100)])
        assert not await cache.exists(key)
        assert await cache.hgetall(ordinary)=={'{"result":"model"}':malformed}
