import os
from datetime import datetime,timedelta
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.services.realtime_voice_retention_service import VoiceRetentionService
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step034_content_retention import seed
from tests.test_realtime_voice_step034_delete import ADMIN
from tests.test_realtime_voice_step034_metrics import (
    test_delete_metrics_reflect_commit_not_rolled_back_changes,
    test_expiry_scan_counts_attempts_but_cancellation_only_once,
)
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_production_retention_counters_in_real_redis(card_env,runtime):
    factory,call_id=card_env;cache=runtime[2];now=datetime.utcnow()
    await seed(factory,call_id,now,now+timedelta(days=1))
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    service=VoiceRetentionService(session_factory=factory,cache=cache,metrics=VoiceMetrics(cache,deadline_seconds=1))
    await service.delete_call(call_id=call_id,admin=ADMIN)
    keys=[key async for key in cache.scan_iter(match='voice.retention.*')]
    assert {key.split(':')[0] for key in keys}=={'voice.retention.fence','voice.retention.single_call_delete'}
    for key in keys:
        assert 172790<=await cache.ttl(key)<=172800
        assert call_id not in key
        assert set((await cache.hgetall(key)).values())=={'1'}
    assert {key:await cache.get(key) for key in shared}==shared
