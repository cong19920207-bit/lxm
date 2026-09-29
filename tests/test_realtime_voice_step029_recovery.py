"""Durable worker recovery; SQLite covers state, MySQL races tested separately."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from backend.models.realtime_voice import VoiceMemoryJob, VoiceMemoryTrace
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from tests.test_realtime_voice_step028_jobs import storage, memory_env, add_turn, Writer, Gate


@pytest.mark.asyncio
async def test_poll_classifies_expired_worker_and_rejects_stale_write(memory_env):
    factory, call = memory_env
    turn_id = await add_turn(factory, call)
    writer = Writer()
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    service = VoiceMemoryService(session_factory=factory, gate=Gate(), model=model, writer=writer)
    await service.enqueue(call_id=call, turn_id=turn_id)
    async with factory() as db:
        job = await db.scalar(select(VoiceMemoryJob))
        job.status = 'processing'
        job.lease_owner = 'dead-worker'
        job.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
        job.attempt_count = 1
        job_id = job.id
        await db.commit()
    item = dict(memory_type='user', stable_key='旅行-计划-日本', content='下月去日本')
    # A stale owner may not write even before a replacement claims the job.
    assert await service._write(call, job_id, 'dead-worker', 1, 1, item) == 'cancelled'
    assert not writer.calls
    assert await service.poll() == ['failed']
    assert await service.poll() == []
    async with factory() as db:
        job = await db.get(VoiceMemoryJob, job_id)
        assert job.attempt_count == 1 and job.status == 'failed'
        assert job.fail_reason == 'recovery_snapshot_required'
        assert job.lease_owner is None
        assert len((await db.scalars(select(VoiceMemoryTrace))).all()) == 0
    assert len(writer.calls) == 0


@pytest.mark.asyncio
async def test_live_lease_is_not_reclaimed_or_overwritten(memory_env):
    factory, call = memory_env
    turn_id = await add_turn(factory, call)
    async def forbidden(prompt):
        pytest.fail('live lease was reclaimed')
    service = VoiceMemoryService(session_factory=factory, gate=Gate(), model=forbidden, writer=Writer())
    await service.enqueue(call_id=call, turn_id=turn_id)
    async with factory() as db:
        job = await db.scalar(select(VoiceMemoryJob))
        job.status = 'processing'
        job.lease_owner = 'live-worker'
        job.lease_expires_at = datetime.utcnow() + timedelta(seconds=120)
        job.attempt_count = 1
        await db.commit()
    assert await service.poll() == []
    assert await service.process_next(call_id=call) == 'busy'


@pytest.mark.asyncio
async def test_partial_recovery_requires_snapshot_and_rejects_old_finish(memory_env):
    factory, call = memory_env
    turn_id = await add_turn(factory, call)
    writer = Writer()
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    service = VoiceMemoryService(session_factory=factory, gate=Gate(), model=model, writer=writer)
    await service.enqueue(call_id=call, turn_id=turn_id)
    async with factory() as db:
        job = await db.scalar(select(VoiceMemoryJob))
        job.status = 'processing'
        job.lease_owner = 'old-worker'
        job.lease_expires_at = datetime.utcnow() + timedelta(seconds=120)
        job.attempt_count = 1
        job_id = job.id
        await db.commit()
    item = dict(memory_type='user', stable_key='旅行-计划-日本', content='下月去日本')
    assert await service._write(call, job_id, 'old-worker', 1, 1, item) == 'written'
    async def changed_model(prompt):
        pytest.fail('partial recovery must not regenerate a different atom set')
    service.model = changed_model
    async with factory() as db:
        job = await db.get(VoiceMemoryJob, job_id)
        job.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
        await db.commit()
    assert await service._finish(call, job_id, 'old-worker', 'failed', 'late_failure') == 'processing'
    assert await service.poll() == ['failed']
    assert await service._finish(call, job_id, 'old-worker', 'success', None) == 'failed'
    assert len(writer.calls) == 1
    async with factory() as db:
        traces = (await db.scalars(select(VoiceMemoryTrace))).all()
        assert [(t.call_id, t.turn_index, t.doc_id, t.pipeline_version) for t in traces] == [
            (call, 1, writer.calls[0], 'voice_memory_v1')]
        job = await db.get(VoiceMemoryJob, job_id)
        assert job.status == 'failed' and job.attempt_count == 1
        assert job.fail_reason == 'recovery_snapshot_required'


@pytest.mark.asyncio
async def test_fence_preserves_success_and_permanently_cancels_uncommitted(memory_env):
    from backend.models.realtime_voice import VoiceCall
    factory, call = memory_env
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    writer = Writer()
    service = VoiceMemoryService(session_factory=factory, gate=Gate(), model=model, writer=writer)
    for index in (1, 2):
        await service.enqueue(call_id=call, turn_id=await add_turn(factory, call, index))
    assert await service.process_next(call_id=call) == 'success'
    async with factory() as db:
        assert await service.stage_deletion_fence(db, call_id=call) == 1
        await db.commit()
    async with factory() as db:
        first_fence = (await db.scalar(select(VoiceCall))).deletion_fence_at
        assert first_fence is not None
        assert await service.stage_deletion_fence(db, call_id=call) == 0
        await db.commit()
    assert await service.poll() == []
    assert await service.process_next(call_id=call) == 'idle'
    async with factory() as db:
        jobs = (await db.scalars(select(VoiceMemoryJob).order_by(VoiceMemoryJob.turn_index))).all()
        assert [j.status for j in jobs] == ['success', 'cancelled']
        assert (await db.scalar(select(VoiceCall))).deletion_fence_at == first_fence
        assert len((await db.scalars(select(VoiceMemoryTrace))).all()) == 1
    assert len(writer.calls) == 1


@pytest.mark.asyncio
async def test_compensation_adds_only_missing_closed_turn_jobs(memory_env):
    from backend.models.realtime_voice import VoiceCall
    factory, call = memory_env
    async def model(prompt):
        return '{"memory_items":[]}'
    service = VoiceMemoryService(session_factory=factory, gate=Gate(), model=model, writer=Writer())
    first = await add_turn(factory, call, 1)
    second = await add_turn(factory, call, 2)
    await add_turn(factory, call, 3, turn_status='collecting')
    await service.enqueue(call_id=call, turn_id=first)
    assert await service.process_next(call_id=call) == 'skipped'
    assert (await service.compensate(call_id=call))['status'] == 'not_ended'
    async with factory() as db:
        row = await db.scalar(select(VoiceCall))
        row.status = 'ended'
        row.ended_at = datetime.utcnow()
        await db.commit()
    result = await service.compensate(call_id=call)
    assert result['created'] == [(second, 'voice_memory_v1')]
    assert result['turn_keys'] == [(call, 1), (call, 2)]
    assert result['job_keys'] == [(first, 'voice_memory_v1'), (second, 'voice_memory_v1')]
    assert result['trace_keys'] == []
    assert (await service.compensate(call_id=call))['created'] == []
    async with factory() as db:
        await service.stage_deletion_fence(db, call_id=call)
        await db.commit()
    assert (await service.compensate(call_id=call))['status'] == 'cancelled'
    async with factory() as db:
        jobs = (await db.scalars(select(VoiceMemoryJob).order_by(VoiceMemoryJob.turn_index))).all()
        assert [(j.turn_id, j.status, j.attempt_count) for j in jobs] == [(first, 'skipped', 1), (second, 'cancelled', 0)]
