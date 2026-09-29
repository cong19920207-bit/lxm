from datetime import datetime,timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall,VoiceCallTurn,VoiceMemoryJob,VoicePostprocessJob,VoiceFollowupJob,VoiceMemoryTrace,VoiceCrisisRecord
from backend.models.admin_operation_log import AdminOperationLog
from backend.services.realtime_voice_retention_service import VoiceRetentionService
from tests.test_realtime_voice_step021_cards import card_env,memory_env,storage
from tests.test_realtime_voice_step034_content_retention import seed,Cache

ADMIN=SimpleNamespace(id=1,username='delete-test',role='super_admin')


@pytest.mark.asyncio
async def test_delete_clears_content_keeps_trace_and_audits_each_attempt(card_env):
    factory,call_id=card_env;now=datetime.utcnow()
    turn_id,crisis_id,jobs,trace_id=await seed(factory,call_id,now,now+timedelta(days=1))
    async with factory() as db:
        job=await db.get(VoicePostprocessJob,jobs[1]);job.status='pending'
        followup=await db.get(VoiceFollowupJob,jobs[2]);followup.status='pending'
        trace=await db.get(VoiceMemoryTrace,trace_id)
        retained={col.name:getattr(trace,col.name) for col in trace.__table__.columns}
        await db.commit()
    cache=Cache();key=f'voice:session_context:{call_id}';cache.values[key]='private'
    service=VoiceRetentionService(session_factory=factory,cache=cache)
    await service.delete_call(call_id=call_id,admin=ADMIN)
    await service.delete_call(call_id=call_id,admin=ADMIN)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        assert call.deletion_fence_at and call.deleted_at and call.deleted_by==1
        assert all(getattr(call,field) is None for field in ['sort_seq','call_summary','summary_reasoning','unfinished_topics','user_emotion','assistant_emotion'])
        turn=await db.get(VoiceCallTurn,turn_id)
        assert (turn.user_text_final,turn.assistant_text_effective,turn.assistant_text_generated)==(None,None,None)
        assert turn.content_clear_reason=='admin_deleted' and turn.memory_status=='success'
        assert (await db.get(VoiceMemoryJob,jobs[0])).status=='success'
        assert (await db.get(VoiceMemoryJob,jobs[0])).extraction_snapshot is None
        assert (await db.get(VoicePostprocessJob,jobs[1])).status=='cancelled'
        assert (await db.get(VoiceFollowupJob,jobs[2])).status=='cancelled'
        assert (await db.get(VoiceFollowupJob,jobs[2])).content==''
        assert (await db.get(VoiceCrisisRecord,crisis_id)).content_plaintext is None
        trace=await db.get(VoiceMemoryTrace,trace_id)
        assert {col.name:getattr(trace,col.name) for col in trace.__table__.columns}==retained
        logs=list((await db.scalars(select(AdminOperationLog).where(AdminOperationLog.module=='voice_calls'))).all())
        assert [row.action for row in logs].count('delete_attempt')==2
        assert [row.action for row in logs].count('delete')==2
        assert all('private' not in str(row.before_value)+str(row.after_value)+str(row.target_description) for row in logs)
    assert key not in cache.values


@pytest.mark.asyncio
async def test_delete_cache_failure_rolls_back_but_attempt_audit_survives(card_env):
    factory,call_id=card_env;now=datetime.utcnow()
    turn_id,_,_,_=await seed(factory,call_id,now,now+timedelta(days=1))
    class FailingCache:
        async def delete(self,key):raise ConnectionError('private-unavailable')
    with pytest.raises(ConnectionError):
        await VoiceRetentionService(session_factory=factory,cache=FailingCache()).delete_call(call_id=call_id,admin=ADMIN)
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        assert call.deleted_at is None and call.deletion_fence_at is None
        assert (await db.get(VoiceCallTurn,turn_id)).user_text_final is not None
        logs=list((await db.scalars(select(AdminOperationLog).where(AdminOperationLog.module=='voice_calls'))).all())
        assert [row.action for row in logs]==['delete_attempt']


@pytest.mark.asyncio
@pytest.mark.parametrize('role',['super_admin','ops_admin','observer','ai_trainer','tech_ops'])
async def test_delete_http_role_and_body_unrecoverable(card_env,role):
    from fastapi import FastAPI
    from httpx import AsyncClient,ASGITransport
    from backend.database import get_db
    from backend.routers.admin.voice_records import router
    from backend.utils.admin_auth import get_current_admin
    from backend.services.realtime_voice_retention_service import build_voice_retention_service
    factory,call_id=card_env;now=datetime.utcnow()
    await seed(factory,call_id,now,now+timedelta(days=1))
    app=FastAPI();app.include_router(router,prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=1,username='test',role=role)
    async def db_session():
        async with factory() as db:yield db
    app.dependency_overrides[get_db]=db_session
    app.dependency_overrides[build_voice_retention_service]=lambda:VoiceRetentionService(session_factory=factory,cache=Cache())
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        result=await client.delete('/api/admin/voice/calls/'+call_id)
        assert result.status_code==(200 if role=='super_admin' else 403)
        if role=='super_admin':
            assert result.headers['cache-control']=='no-store'
            listing=await client.get('/api/admin/voice/calls')
            assert listing.json()['data']['items']==[]
            exported=await client.post('/api/admin/voice/calls/export',json={'call_ids':[call_id]})
            assert exported.status_code==200 and exported.json()['data']['items']==[]
            transcript=await client.get('/api/admin/voice/calls/'+call_id+'/turns')
            assert '下月去日本' not in transcript.text and 'generated-private' not in transcript.text
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        assert bool(call.deleted_at)==(role=='super_admin')
