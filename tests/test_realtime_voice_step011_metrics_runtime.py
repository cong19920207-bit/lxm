import os
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step012_gateway import session
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_call01_lifecycle_actual_database_and_metric_store(card_env,runtime,monkeypatch):
    import backend.services.realtime_voice_gateway_service as module
    from backend.database import Base
    from backend.models.relationship import Relationship
    async with card_env[0].kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[Relationship.__table__])
    cache=runtime[2];gateway=await session(card_env[0]);gateway.cache=cache;gateway.metrics=VoiceMetrics(cache,deadline_seconds=1)
    async def inputs(*args,**kwargs):return {}
    async def model(prompt):return '{"answer":false,"delay_seconds":0,"opening_text":""}'
    monkeypatch.setattr(module,'call_decision_inputs',inputs)
    gateway.decision_model=model;gateway.script['call_answer']['prompt_template']='synthetic decision'
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    await gateway.lifecycle()
    keys=[key async for key in cache.scan_iter(match='voice.call01.*')]
    names={key.split(':')[0] for key in keys}
    assert {'voice.call01.output','voice.call01.decision','voice.call01.ringing_result','voice.call01.provider_ready'}<=names
    for key in keys:
        assert 172790<=await cache.ttl(key)<=172800
        values=await cache.hgetall(key)
        assert gateway.call.call_id not in str(values) and 'synthetic' not in str(values)
        if key.startswith('voice.call01.ringing_result:'):assert values=={'{"result":"missed"}':'1'}
    assert {key:await cache.get(key) for key in shared}==shared
