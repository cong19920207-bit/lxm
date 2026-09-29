"""Real MySQL locking for recovery and partially committed deletion races."""
import asyncio
import os

import pytest
from sqlalchemy import select

from backend.models.realtime_voice import VoiceMemoryJob, VoiceMemoryTrace
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from tests.test_realtime_voice_m4_runtime import containers, runtime
from tests.test_realtime_voice_step028_runtime import memory_env
from tests.test_realtime_voice_step028_jobs import add_turn, Writer, Gate
from tests.test_realtime_voice_step029_recovery import (
    test_poll_classifies_expired_worker_and_rejects_stale_write,
    test_live_lease_is_not_reclaimed_or_overwritten,
    test_partial_recovery_requires_snapshot_and_rejects_old_finish,
    test_fence_preserves_success_and_permanently_cancels_uncommitted,
    test_compensation_adds_only_missing_closed_turn_jobs,
)

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M5_RUNTIME') != '1', reason='isolated MySQL/Redis opt-in')


@pytest.mark.asyncio
async def test_fence_waits_for_active_commit_then_stops_remaining_atoms(memory_env):
    factory, call = memory_env
    writer = Writer()
    entered, release, deleting = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def slow_writer(**kw):
        entered.set()
        await release.wait()
        return await writer(**kw)
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"},{"memory_type":"user","stable_key":"旅行-城市-京都","content":"想去京都"}]}'
    service = VoiceMemoryService(session_factory=factory, gate=Gate(), model=model, writer=slow_writer)
    await service.enqueue(call_id=call, turn_id=await add_turn(factory, call))
    async def fence():
        async with factory() as db:
            deleting.set()
            result = await service.stage_deletion_fence(db, call_id=call)
            await db.commit()
            return result
    worker = asyncio.create_task(service.process_next(call_id=call))
    deletion = None
    try:
        await asyncio.wait_for(entered.wait(), 3)
        deletion = asyncio.create_task(fence())
        await asyncio.wait_for(deleting.wait(), 2)
        await asyncio.sleep(.1)
        assert not deletion.done(), 'deletion bypassed the active vector transaction'
        release.set()
        assert await asyncio.wait_for(deletion, 3) == 1
        assert await asyncio.wait_for(worker, 3) == 'cancelled'
    finally:
        release.set()
        await asyncio.gather(worker, *([deletion] if deletion else []), return_exceptions=True)
    assert len(writer.calls) == 1
    async with factory() as db:
        assert (await db.scalar(select(VoiceMemoryJob))).status == 'cancelled'
        assert [t.doc_id for t in (await db.scalars(select(VoiceMemoryTrace))).all()] == writer.calls
    assert await service.poll() == []
