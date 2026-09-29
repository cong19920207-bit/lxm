"""Actual MySQL/Redis; synthetic model/vector, no external Provider charges."""
import asyncio
import os
from datetime import datetime

import pytest
from sqlalchemy import select

from backend.models.realtime_voice import VoiceCall
from backend.services.realtime_voice_session_context_service import VoiceSessionContext
from backend.services.realtime_voice_recall_service import VoiceRecallCoordinator
from tests.test_realtime_voice_m4_runtime import containers, runtime
from tests.test_realtime_voice_step028_jobs import add_turn
from tests.test_realtime_voice_step030_recall import service, recall, Adapter, script

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M5_RUNTIME')!='1',reason='isolated MySQL/Redis opt-in')


@pytest.mark.asyncio
async def test_late_result_real_cache_ownership_reconnect_and_fence(runtime):
    factory,call,cache=runtime
    ctx=VoiceSessionContext(cache=cache,session_factory=factory)
    out=await recall(service(ctx),call_id=call,adapter=Adapter('next_turn'))
    assert out.mode=='next_turn_cached'
    assert (await ctx.query(call_id=call,user_id=1,turn_index=1)).items==()
    assert len((await ctx.query(call_id=call,user_id=1,turn_index=2)).items)==1
    assert await cache.ttl('voice:session_context:'+call)>0
    assert (await ctx.query(call_id=call,user_id=2,turn_index=2)).status=='forbidden'
    restored=VoiceSessionContext(cache=cache,session_factory=factory)
    async def never(*args,**kwargs): raise AssertionError('long-term query repeated')
    second=await recall(service(restored,embed=never,search=never),call_id=call,question_id='q2',turn_index=2)
    assert second.source=='topic_cache' and second.mode=='current_turn_requested'
    async with factory() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call)); row.deletion_fence_at=datetime.utcnow(); await db.commit()
    a=Adapter(); third=await recall(service(restored),call_id=call,question_id='q3',turn_index=3,adapter=a)
    assert third.status=='context_unavailable' and not a.calls


@pytest.mark.asyncio
async def test_coordinator_actual_safe_turn_dedup_and_stop(runtime):
    factory,call,cache=runtime
    await add_turn(factory,call)
    ctx=VoiceSessionContext(cache=cache,session_factory=factory)
    a=Adapter()
    coordinator=VoiceRecallCoordinator(call_id=call,user_id=1,session_factory=factory,service=service(ctx),adapter=a,script=script())
    for _ in range(30): coordinator.submit('q1')
    await asyncio.gather(*list(coordinator.tasks.values()))
    assert len(a.calls)==1
    await coordinator.close()
    coordinator.submit('q2')
    assert not coordinator.tasks and coordinator.preamble==''
