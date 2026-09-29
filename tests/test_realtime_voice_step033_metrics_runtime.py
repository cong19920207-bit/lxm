import os
import pytest
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step033_metrics import (
    test_admin_metric_role_results_and_audit,
    test_admin_metric_failure_does_not_return_partial_export,
)
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_application_adapter_actual_redis_and_no_shared_writes(card_env,runtime,monkeypatch):
    from httpx import ASGITransport,AsyncClient
    import backend.redis_client as redis_module
    from backend.services.realtime_voice_metric_service import ApplicationVoiceMetrics
    from tests.test_realtime_voice_step033_metrics import application
    from tests.test_realtime_voice_step031_metrics import CounterCache
    factory,call_id=card_env;cache=runtime[2]
    async def redis():return cache
    monkeypatch.setattr(redis_module,'get_redis',redis)
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    app=application(factory,'observer',CounterCache());app.state.voice_metrics=ApplicationVoiceMetrics()
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/api/admin/voice/calls/'+call_id)).status_code==200
        assert (await client.post('/api/admin/voice/calls/export',json={'call_ids':[call_id]})).status_code==403
    keys=[key async for key in cache.scan_iter(match='voice.admin_record.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.admin_record.authorization','voice.admin_record.result','voice.admin_record.audit'}
    for key in keys:
        assert 172790<=await cache.ttl(key)<=172800
        assert call_id not in str(await cache.hgetall(key))
    assert {key:await cache.get(key) for key in shared}==shared
