import os
import pytest
from backend.services.realtime_voice_barge_in_service import BargeObservations,BargeInController
from backend.services.realtime_voice_backchannel_service import BackchannelFilter
from backend.services.realtime_voice_metric_service import VoiceMetrics
from backend.constants.realtime_voice_config import get_default_voice_call_script
from tests.test_realtime_voice_step017_metrics import Adapter
from tests.test_realtime_voice_step015_turns import event
from tests.test_realtime_voice_step033_runtime import containers,runtime
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated stores')


@pytest.mark.asyncio
async def test_real_filter_and_stop_counters(runtime):
    _,_,cache=runtime;obs=BargeObservations()
    shared={'llm_stats':'a','llm_response_times':'b','content_block_count:20260919':'c'}
    for key,value in shared.items():await cache.set(key,value)
    async def noop(*a,**k):pass
    f=BackchannelFilter(get_default_voice_call_script()['barge_in'],noop,noop,noop,obs)
    await f.consume(event('c',1,'user_speech_started',question='q1'),playing='q0')
    await f.consume(event('c',2,'asr_final','嗯',question='q1'),playing='q0')
    await f.close()
    c=BargeInController(Adapter(enabled=False),noop,obs)
    await c.upgrade('r1');await c.stopped('r1',100);c.finish_observations()
    events=obs.drain()
    assert ('voice.barge_in.decision',{'result':'backchannel','source':'filter'},1) in events
    assert await VoiceMetrics(cache,deadline_seconds=1).emit_many(events)
    keys=[key async for key in cache.scan_iter(match='voice.barge_in.*')]
    assert len(keys)>=3
    for key in keys:assert 172790<=await cache.ttl(key)<=172800
    assert {key:await cache.get(key) for key in shared}==shared
