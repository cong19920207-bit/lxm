import os
from datetime import datetime,timedelta
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceMemoryJob
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from tests.test_realtime_voice_step028_runtime import containers,runtime,memory_env
from tests.test_realtime_voice_step028_jobs import add_turn,Gate
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_retry_and_fence_actual_stores(runtime,memory_env):
    factory,call=memory_env;cache=runtime[2]
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    async def model(_):raise RuntimeError('unavailable')
    metrics=VoiceMetrics(cache,deadline_seconds=1)
    svc=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,metrics=metrics)
    await svc.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    assert await svc.process_next(call_id=call)=='failed'
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob));assert job.next_retry_at is not None
        job.next_retry_at=datetime.utcnow()-timedelta(seconds=1);await db.commit()
    assert await svc.process_next(call_id=call)=='failed'
    for count in (1,0):
        async with factory() as db:
            assert await svc.stage_deletion_fence(db,call_id=call)==count
            await db.commit();await flush_voice_metrics(db,metrics)
    keys=[key async for key in cache.scan_iter(match='voice.memory_job.*')]
    async def counter(name):return await cache.hgetall(next(k for k in keys if k.startswith('voice.memory_job.'+name+':')))
    assert await counter('claim')=={'{"phase":"first"}':'1','{"phase":"retry"}':'1'}
    assert await counter('retry')=={'{"reason":"extract_unavailable","source":"automatic"}':'2'}
    assert await counter('fence_cancel')=={'{}':'1'}
    for key in keys:assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared

# Same ownership/rollback branches with real MySQL transactions.
from tests.test_realtime_voice_step033_runtime import card_env
from tests.test_realtime_voice_step034_metrics import (
    test_delete_metrics_reflect_commit_not_rolled_back_changes,
    test_expiry_emits_memory_job_drop_after_commit,
)
