import os
import pytest
from backend.services.relationship_service import RelationshipService
from backend.services.realtime_voice_metric_service import VoiceMetrics,flush_voice_metrics
from tests.test_realtime_voice_step022_runtime import containers,runtime,memory_env,growth_env
from tests.test_realtime_voice_step022_metrics import cross_modal
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_growth_crossmodal_actual_stores(runtime,growth_env):
    factory,call_id=growth_env;cache=runtime[2];metrics=VoiceMetrics(cache,deadline_seconds=1)
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    async with factory() as db:
        await RelationshipService(db).add_voice_growth(1,65,call_id)
        await db.commit();await flush_voice_metrics(db,metrics)
    await cross_modal(factory,metrics,False)
    keys=[key async for key in cache.scan_iter(match='voice.*')]
    assert len(keys)==7
    for key in keys:assert 172790<=await cache.ttl(key)<=172800
    points=next(key for key in keys if key.startswith('voice.growth.points:'))
    assert await cache.hgetall(points)=={'{}':'10'}
    assert {key:await cache.get(key) for key in shared}==shared
