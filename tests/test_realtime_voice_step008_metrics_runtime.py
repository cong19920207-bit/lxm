import os
from datetime import datetime,timedelta,timezone
import pytest
from backend.services.realtime_voice_quota_service import VoiceQuotaService,ConnectedMeter
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_quota_committed_real_storage_and_zero_shared_writes(runtime):
    factory,call_id,cache=runtime;now=datetime.now(timezone.utc);metrics=VoiceMetrics(cache,deadline_seconds=1)
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    quota=VoiceQuotaService(metrics=metrics);meter=ConnectedMeter(call_id=call_id,user_id=1,daily_seconds=3,grace_limit=5)
    async with factory() as db:
        await quota.observe(db,meter,connected=True,monotonic=0,now=now)
        await quota.observe(db,meter,connected=True,monotonic=8,now=now+timedelta(seconds=8))
        await quota.settle(db,meter);await db.commit();await flush_voice_metrics(db,metrics)
        await quota.settle(db,meter);await db.commit();await flush_voice_metrics(db,metrics)
    keys=[key async for key in cache.scan_iter(match='voice.quota.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.quota.usage_slice','voice.quota.usage_seconds','voice.quota.balance_zero',
        'voice.quota.grace','voice.quota.grace_seconds','voice.quota.billing_input_seconds','voice.quota.deduplicated'}
    for key in keys:
        assert 172790<=await cache.ttl(key)<=172800
        assert call_id not in str(await cache.hgetall(key))
        if key.startswith('voice.quota.billing_input_seconds:'):assert list((await cache.hgetall(key)).values())==['3']
        if key.startswith('voice.quota.grace_seconds:'):assert list((await cache.hgetall(key)).values())==['5']
    assert {key:await cache.get(key) for key in shared}==shared
