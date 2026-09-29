import json
import os
from datetime import datetime, timezone
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step033_runtime import containers, runtime, card_env
from tests.test_realtime_voice_step031_jobs import summary_env, service
from tests.test_realtime_voice_step031_metrics import (
    test_summary_transition_events_are_closed_and_not_replayed,
    test_reasoning_expiry_counts_actual_clears_only,
    test_metric_failure_does_not_change_committed_summary,
)

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated store opt-in')


@pytest.mark.asyncio
async def test_actual_summary_counter_ttl_and_shared_keys_unchanged(summary_env,runtime):
    factory,call_id=summary_env;cache=runtime[2]
    shared={'llm_stats':'keep-a','llm_response_times':'keep-b','content_block_count:20260919':'keep-c'}
    for key,value in shared.items():await cache.set(key,value)
    worker=service(factory);worker.metrics=VoiceMetrics(cache,deadline_seconds=1)
    await worker.enqueue(call_id=call_id);assert await worker.process(call_id=call_id)=='ready'
    await worker.process(call_id=call_id)
    keys=sorted([key async for key in cache.scan_iter(match='voice.summary.*')])
    assert {key.split(':')[0] for key in keys}=={'voice.summary.eligible','voice.summary.result','voice.summary.card_update'}
    values={key.split(':')[0]:await cache.hgetall(key) for key in keys}
    assert values=={'voice.summary.eligible':{'{"result":"eligible"}':'1'},
        'voice.summary.result':{'{"result":"ready"}':'1'},'voice.summary.card_update':{'{"status":"ready"}':'1'}}
    ttls=[await cache.ttl(key) for key in keys]
    assert all(172790 <= ttl <= 172800 for ttl in ttls)
    assert call_id not in json.dumps(values)
    assert {key:await cache.get(key) for key in shared}==shared


@pytest.mark.asyncio
async def test_redis_batch_corruption_does_not_leave_partial_counts(runtime):
    cache=runtime[2];day=datetime.now(timezone.utc).strftime('%Y%m%d')
    first='voice.summary.result:'+day;second='voice.summary.card_update:'+day
    await cache.set(second,'corrupt')
    metrics=VoiceMetrics(cache,deadline_seconds=1)
    assert await metrics.emit_many([('voice.summary.result',{'result':'ready'},1),
        ('voice.summary.card_update',{'status':'ready'},1)]) is False
    assert await cache.exists(first)==0 and await cache.get(second)=='corrupt'
