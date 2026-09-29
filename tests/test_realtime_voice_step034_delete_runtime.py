import asyncio
import os
from datetime import datetime,timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.realtime_voice import VoiceMemoryJob,VoiceMemoryTrace,VoiceUsageLedger,VoiceCall,VoiceCallTurn,VoiceFollowupJob,VoiceCrisisRecord
from backend.models.relationship_growth_log import RelationshipGrowthLog
from backend.services.realtime_voice_retention_service import VoiceRetentionService
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step034_content_retention import seed
from tests.test_realtime_voice_step034_delete import (ADMIN,
    test_delete_clears_content_keeps_trace_and_audits_each_attempt,
    test_delete_cache_failure_rolls_back_but_attempt_audit_survives,
    test_delete_http_role_and_body_unrecoverable)

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


@pytest.mark.asyncio
async def test_delete_preserves_full_ledger_growth_trace_sets(card_env,runtime):
    factory,call_id=card_env;_,_,cache=runtime;now=datetime.utcnow()
    await seed(factory,call_id,now,now+timedelta(days=1))
    async with factory() as db:
        db.add(VoiceUsageLedger(call_id=call_id,segment_seq=1,free_seconds_used=30,extra_seconds_used=0,usage_type='free'))
        db.add(RelationshipGrowthLog(user_id=1,action_type='voice_call',points=5,source_type='voice_call',source_id=call_id))
        await db.commit()
    async def preserved():
        async with factory() as db:
            result={}
            for model in (VoiceMemoryTrace,VoiceUsageLedger,RelationshipGrowthLog):
                rows=list((await db.scalars(select(model).order_by(model.id))).all())
                result[model.__tablename__]=[{c.name:getattr(row,c.name) for c in model.__table__.columns} for row in rows]
            return result
    before=await preserved()
    fields={VoiceCall:('sort_seq','call_summary','summary_reasoning','unfinished_topics','user_emotion','assistant_emotion'),
        VoiceCallTurn:('user_text_final','assistant_text_effective','assistant_text_generated'),
        VoiceMemoryJob:('extraction_snapshot',),VoiceFollowupJob:('content',),
        VoiceCrisisRecord:('content_plaintext','matched_keyword')}
    async def content_objects():
        async with factory() as db:
            objects=set()
            for model,names in fields.items():
                for row in (await db.scalars(select(model).where(model.call_id==call_id))).all():
                    for name in names:
                        if getattr(row,name) not in (None,''):objects.add((model.__tablename__,row.id,name))
            return objects
    deletion_set=await content_objects()
    assert deletion_set
    key=f'voice:session_context:{call_id}';await cache.set(key,'synthetic-private-context')
    unrelated='voice:session_context:unrelated-call';await cache.set(unrelated,'preserve')
    await cache.set(f'voice:quota:{call_id}','{"billable_seconds":30}')
    cache_before={key:await cache.get(key) async for key in cache.scan_iter(match='voice:*')}
    report=await VoiceRetentionService(session_factory=factory,cache=cache).delete_call(call_id=call_id,admin=ADMIN)
    assert report['cache_keys']==[key] and await cache.get(key) is None
    assert await cache.get(unrelated)=='preserve'
    assert await preserved()==before
    assert await content_objects()==set()
    cache_after={key:await cache.get(key) async for key in cache.scan_iter(match='voice:*')}
    assert cache_after=={name:value for name,value in cache_before.items() if name!=key}
    async with factory() as db:
        rows=list((await db.scalars(select(VoiceCallTurn).where(VoiceCallTurn.call_id==call_id))).all())
        assert all(row.user_text_final is None and row.assistant_text_effective is None and row.assistant_text_generated is None for row in rows)


@pytest.mark.asyncio
async def test_delete_waits_for_committed_memory_then_fences(card_env,runtime,monkeypatch):
    factory,call_id=card_env;_,_,cache=runtime;now=datetime.utcnow()
    _,_,jobs,_=await seed(factory,call_id,now,now+timedelta(days=1))
    async with factory() as db:
        job=await db.get(VoiceMemoryJob,jobs[0]);job.status='processing';await db.commit()
    reached=asyncio.Event();original=AsyncSession.scalars
    async def scalars(db,statement,*args,**kwargs):
        if getattr(statement,'column_descriptions',[]) and statement.column_descriptions[0].get('entity') is VoiceMemoryJob:reached.set()
        return await original(db,statement,*args,**kwargs)
    async with factory() as writer:
        job=await writer.scalar(select(VoiceMemoryJob).where(VoiceMemoryJob.id==jobs[0]).with_for_update())
        monkeypatch.setattr(AsyncSession,'scalars',scalars)
        task=asyncio.create_task(VoiceRetentionService(session_factory=factory,cache=cache).delete_call(call_id=call_id,admin=ADMIN))
        try:
            await asyncio.wait_for(reached.wait(),5)
            assert not task.done()
            writer.add(VoiceMemoryTrace(call_id=call_id,turn_index=1,doc_id='committed-before-fence',memory_type='user',
                stable_key='保留事项',pipeline_version='retention-test',written_at=now))
            job.status='success';await writer.commit()
            await asyncio.wait_for(task,5)
        finally:
            if not task.done():task.cancel()
            await asyncio.gather(task,return_exceptions=True)
    async with factory() as db:
        assert await db.scalar(select(VoiceMemoryTrace.id).where(VoiceMemoryTrace.doc_id=='committed-before-fence'))
        assert (await db.get(VoiceMemoryJob,jobs[0])).status=='success'
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        assert call.deletion_fence_at and call.deleted_at


@pytest.mark.asyncio
async def test_partial_memory_commit_keeps_trace_and_cancels_remaining_atoms(card_env,runtime):
    factory,call_id=card_env;_,_,cache=runtime;now=datetime.utcnow()
    _,_,jobs,trace_id=await seed(factory,call_id,now,now+timedelta(days=1))
    async with factory() as db:
        job=await db.get(VoiceMemoryJob,jobs[0]);job.status='processing'
        await db.commit()
    await VoiceRetentionService(session_factory=factory,cache=cache).delete_call(call_id=call_id,admin=ADMIN)
    async with factory() as db:
        job=await db.get(VoiceMemoryJob,jobs[0])
        assert job.status=='cancelled' and job.extraction_snapshot is None
        assert (await db.get(VoiceMemoryTrace,trace_id)).doc_id=='retained-doc'
