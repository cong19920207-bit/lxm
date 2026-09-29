import os,json
from uuid import uuid4
import pytest
from backend.services.realtime_voice_lease_service import VoiceLeaseService
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_actual_lease_results_and_independent_counters(runtime):
    cache=runtime[2];ends=[]
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    async def end(**kwargs):ends.append(kwargs)
    lease=VoiceLeaseService(cache,end_call=end);first=str(uuid4());other=str(uuid4())
    assert await lease.acquire(user_id=1,call_id=first,ttl_ms=15000,global_limit=1)==(True,'acquired')
    assert await lease.acquire(user_id=1,call_id=other,ttl_ms=15000,global_limit=1)==(False,'user_busy')
    assert await lease.acquire(user_id=2,call_id=other,ttl_ms=15000,global_limit=1)==(False,'capacity_full')
    assert await lease.renew(user_id=1,call_id=first,ttl_ms=15000)
    assert not await lease.release(user_id=2,call_id=first)
    assert await lease.release(user_id=1,call_id=first)
    assert not await lease.owner_matches(user_id=1,call_id=first)
    assert not await lease.renew(user_id=1,call_id=first,ttl_ms=15000)
    assert ends==[dict(call_id=first,user_id=1,reason='system_error')]
    keys=[key async for key in cache.scan_iter(match='voice.lease.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.lease.acquire','voice.lease.renew','voice.lease.release','voice.lease.owner_mismatch'}
    for key in keys:
        values=await cache.hgetall(key)
        assert set(values.values())=={'1'}
        assert first not in str(values) and other not in str(values)
        assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared
