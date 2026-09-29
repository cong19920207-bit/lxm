import os
import pytest
from backend.services.realtime_voice_metric_service import VoiceMetrics
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step028_runtime import memory_env
from tests.test_realtime_voice_step031_runtime import card_env
from tests.test_realtime_voice_step031_jobs import summary_env
from tests.test_realtime_voice_step032_dispatch import dispatch_env,worker
from tests.test_realtime_voice_step032_metrics import (
    test_consumer_metrics_follow_committed_transitions,
    test_schedule_rollback_discards_events_and_replay_does_not_recount,
    test_missed_transition_owner_flushes_only_after_commit,
    test_summary_topic_candidate_events_share_summary_commit,
)

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_real_followup_send_counter_preserves_shared_keys(dispatch_env,runtime):
    cache=runtime[2]
    shared={'llm_stats':'stable','llm_response_times':'stable','content_block_count:20260919':'stable'}
    for key,value in shared.items():await cache.set(key,value)
    consumer=worker(dispatch_env);consumer.metrics=VoiceMetrics(cache,deadline_seconds=1)
    job_id=dispatch_env[2]
    assert await consumer.process(job_id=job_id)=='sent'
    assert await consumer.process(job_id=job_id)=='sent'
    keys=[key async for key in cache.scan_iter(match='voice.followup.*')]
    assert len(keys)==1 and keys[0].startswith('voice.followup.send:')
    assert await cache.hgetall(keys[0])=={'{"result":"sent"}':'1'}
    assert 172790<=await cache.ttl(keys[0])<=172800
    assert {key:await cache.get(key) for key in shared}==shared
