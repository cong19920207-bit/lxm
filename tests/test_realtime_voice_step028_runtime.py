"""Real isolated MySQL queue/trace/lock evidence; no external model/vector calls."""
import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy import select, func

from backend.database import Base
from backend.models.realtime_voice import VoiceCall, VoiceMemoryJob, VoiceMemoryTrace
from backend.models.relationship import Relationship
from tests.test_realtime_voice_m4_runtime import containers, runtime
from tests.test_realtime_voice_step028_jobs import (
    add_turn, Writer, Gate, test_unique_jobs_ordered_two_routes_and_trace,
    test_model_wait_does_not_hold_call_lock_or_start_duplicate,
    test_risk_empty_low_confidence_and_fence_skip_all_writes,
    test_real_turn_commit_creates_job_and_retains_supplied_confidence,
    test_relationship_is_read_only_model_context, test_poll_consumes_persisted_jobs,
)

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M5_RUNTIME')!='1',reason='isolated MySQL/Redis opt-in')


@pytest_asyncio.fixture
async def memory_env(runtime):
    factory,call,cache=runtime
    tables=[m.__table__ for m in (VoiceMemoryJob,VoiceMemoryTrace,Relationship)]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=tables)
    async with factory() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call))
        row.config_snapshot={**row.config_snapshot,'resolved_script':{'memory':{
            'prompt_template':'提取长期事实','max_items_per_turn':5}}}
        await db.commit()
    try:
        yield factory,call
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=tables)


@pytest.mark.asyncio
async def test_concurrent_enqueue_has_single_job(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    factory,call=memory_env; turn=await add_turn(factory,call)
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),writer=Writer())
    assert await asyncio.gather(*(service.enqueue(call_id=call,turn_id=turn) for _ in range(8)))==['pending']*8
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(VoiceMemoryJob))==1


@pytest.mark.asyncio
async def test_slow_vector_write_does_not_lock_live_call(memory_env):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    factory,call=memory_env; turn=await add_turn(factory,call)
    entered,release=asyncio.Event(),asyncio.Event(); writer=Writer()
    async def slow_writer(**kw):
        entered.set(); await release.wait(); return await writer(**kw)
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=slow_writer)
    await service.enqueue(call_id=call,turn_id=turn)
    task=asyncio.create_task(service.process_next(call_id=call))
    try:
        await asyncio.wait_for(entered.wait(),2)
        # A second worker must not hold the call lock waiting on the first
        # writer's job lock; neither may stall live turn assembly.
        assert await asyncio.wait_for(service.process_next(call_id=call),1)=='busy'
        assert await asyncio.wait_for(service.enqueue(call_id=call,turn_id=turn),1)=='processing'
        second=await add_turn(factory,call,2)
        assert await asyncio.wait_for(service.enqueue(call_id=call,turn_id=second),1)=='pending'
    finally:
        release.set(); await task


@pytest.mark.asyncio
async def test_short_term_candidates_consumed_and_cleared_after_write(memory_env,runtime):
    from backend.services.realtime_voice_memory_service import VoiceMemoryService
    from backend.services.realtime_voice_session_context_service import VoiceSessionContext
    factory,call=memory_env; turn=await add_turn(factory,call,2)
    ctx=VoiceSessionContext(cache=runtime[2],session_factory=factory)
    await ctx.append(call_id=call,user_id=1,kind='candidate',item_id='old',turn_index=1,text='京都要提前订酒店',safe=True)
    async def model(prompt):
        assert '京都要提前订酒店' in prompt
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=Writer(),session_context=ctx)
    await service.enqueue(call_id=call,turn_id=turn)
    assert await service.process_next(call_id=call)=='success'
    items=(await ctx.query(call_id=call,user_id=1,turn_index=3)).items
    assert [v['id'] for v in items if v['kind']=='candidate']==['old']
