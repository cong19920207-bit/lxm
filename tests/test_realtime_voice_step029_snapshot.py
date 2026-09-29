import json
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceMemoryJob, VoiceMemoryTrace
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from tests.test_realtime_voice_step028_jobs import storage, memory_env, add_turn, Writer, Gate


@pytest.mark.asyncio
async def test_retry_reuses_first_atoms_and_only_writes_missing(memory_env):
    factory, call = memory_env
    writer = Writer()
    models = []
    failed = False
    async def model(prompt):
        models.append(prompt)
        assert len(models) == 1, 'retry must not regenerate keys'
        return json.dumps({'memory_items':[
            dict(memory_type='user',stable_key='旅行-计划-日本',content='下月去日本'),
            dict(memory_type='user',stable_key='旅行-城市-京都',content='想去京都')]},ensure_ascii=False)
    async def flaky(**kw):
        nonlocal failed
        if kw['key']=='旅行-城市-京都' and not failed:
            failed=True
            raise RuntimeError('temporary')
        return await writer(**kw)
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=flaky)
    await service.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    assert await service.process_next(call_id=call)=='failed'
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob))
        assert len(job.extraction_snapshot['items'])==2
        assert job.next_retry_at>datetime.utcnow()
        job.next_retry_at=datetime.utcnow()-timedelta(seconds=1)
        await db.commit()
    assert await service.poll()==['success']
    assert len(models)==1 and len(writer.calls)==2
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob))
        assert job.extraction_snapshot is None and job.attempt_count==2
        assert len((await db.scalars(select(VoiceMemoryTrace))).all())==2


@pytest.mark.asyncio
async def test_retry_limit_and_due_time(memory_env):
    factory,call=memory_env
    async def model(prompt): raise RuntimeError('temporary')
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=Writer())
    await service.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    for attempt in range(1,4):
        assert await service.process_next(call_id=call)=='failed'
        async with factory() as db:
            job=await db.scalar(select(VoiceMemoryJob))
            assert job.attempt_count==attempt
            if attempt<3:
                assert job.next_retry_at is not None
                assert await service.poll()==[]
                job.next_retry_at=datetime.utcnow()-timedelta(seconds=1)
                await db.commit()
            else:
                assert job.next_retry_at is None
    assert await service.poll()==[]


@pytest.mark.asyncio
async def test_exhausted_snapshot_is_cleared_at_source_expiry(memory_env):
    from backend.models.realtime_voice import VoiceCallTurn
    factory,call=memory_env
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),writer=Writer())
    turn_id=await add_turn(factory,call)
    await service.enqueue(call_id=call,turn_id=turn_id)
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob))
        job.status='failed';job.attempt_count=3
        job.extraction_snapshot={'version':1,'phase':'ready','items':[], 'dropped':0}
        turn=await db.get(VoiceCallTurn,turn_id)
        turn.effective_text_expires_at=datetime.utcnow()-timedelta(seconds=1)
        await db.commit()
    assert await service.poll()==[]
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob))
        assert job.extraction_snapshot is None and job.status=='cancelled'


@pytest.mark.asyncio
async def test_crash_after_snapshot_resumes_without_model(memory_env):
    import asyncio
    factory,call=memory_env
    writer=Writer()
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    async def crash(**kw):
        # External commit succeeded but the SQL trace was never committed.
        await writer(**kw)
        raise asyncio.CancelledError()
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=crash)
    await service.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    with pytest.raises(asyncio.CancelledError):
        await service.process_next(call_id=call)
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob))
        assert job.extraction_snapshot['phase']=='ready'
        job.lease_expires_at=datetime.utcnow()-timedelta(seconds=1)
        await db.commit()
    async def forbidden(prompt): pytest.fail('restored task called extraction model')
    service.model=forbidden; service.writer=writer
    assert await service.poll()==['failed']
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob))
        assert job.fail_reason=='lease_expired'
        job.next_retry_at=datetime.utcnow()-timedelta(seconds=1)
        await db.commit()
    assert await service.poll()==['success']
    assert len(writer.docs)==1 and len(writer.calls)==2
    async with factory() as db:
        traces=(await db.scalars(select(VoiceMemoryTrace))).all()
        assert [(t.doc_id,t.stable_key) for t in traces]==[(writer.calls[0],'旅行-计划-日本')]


def test_retry_config_legacy_compatibility_and_invalid_values():
    from copy import deepcopy
    from backend.constants.realtime_voice_config import get_default_voice_call_script
    from backend.services.realtime_voice_config_service import validate_voice_bundle
    script=get_default_voice_call_script()
    assert not validate_voice_bundle('voice_call_script',script)
    script['memory'].pop('max_retries');script['memory'].pop('retry_backoff_ms')
    before=deepcopy(script)
    assert not validate_voice_bundle('voice_call_script',script)
    assert script==before
    for retries,delays in [(True,[1000]),(6,[1000]*6),(2,[1000]),(2,[5000,1000]),(1,[99])]:
        script['memory'].update(max_retries=retries,retry_backoff_ms=delays)
        assert any(x['field'].startswith('memory.') for x in validate_voice_bundle('voice_call_script',script))


@pytest.mark.asyncio
async def test_stale_writer_cannot_cancel_success_after_source_expires(memory_env):
    from backend.models.realtime_voice import VoiceCallTurn
    factory,call=memory_env
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=Writer())
    turn_id=await add_turn(factory,call)
    await service.enqueue(call_id=call,turn_id=turn_id)
    assert await service.process_next(call_id=call)=='success'
    async with factory() as db:
        job_id=(await db.scalar(select(VoiceMemoryJob))).id
        (await db.get(VoiceCallTurn,turn_id)).effective_text_expires_at=datetime.utcnow()-timedelta(seconds=1)
        await db.commit()
    await service._write(call,job_id,'stale-owner',1,1,dict(memory_type='user',stable_key='旅行-计划-日本',content='old'))
    async with factory() as db:
        assert (await db.get(VoiceMemoryJob,job_id)).status=='success'
        assert (await db.get(VoiceCallTurn,turn_id)).memory_status=='success'


@pytest.mark.asyncio
async def test_exhausted_job_does_not_block_later_turn_and_cannot_overwrite_it(memory_env):
    factory,call=memory_env
    writer=Writer()
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"新的计划"}]}'
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=writer)
    first=await add_turn(factory,call,1)
    second=await add_turn(factory,call,2)
    for tid in [first,second]: await service.enqueue(call_id=call,turn_id=tid)
    async with factory() as db:
        old=await db.scalar(select(VoiceMemoryJob).where(VoiceMemoryJob.turn_id==first))
        old.status='failed';old.attempt_count=3
        old.extraction_snapshot={'version':1,'phase':'ready','dropped':0,'items':[
            dict(memory_type='user',stable_key='旅行-计划-日本',content='旧的计划')]}
        await db.commit()
    assert await service.poll()==['success']
    async with factory() as db:
        old=await db.scalar(select(VoiceMemoryJob).where(VoiceMemoryJob.turn_id==first))
        old.status='pending'  # Same requeue state the authorized retry service will use.
        await db.commit()
    assert await service.poll()==['skipped']
    assert list(writer.docs.values())==['新的计划']
    assert len(writer.calls)==1
