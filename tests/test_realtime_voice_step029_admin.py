from types import SimpleNamespace
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceMemoryJob, VoiceCall
from backend.models.admin_operation_log import AdminOperationLog
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from tests.test_realtime_voice_step028_jobs import storage,memory_env,add_turn,Writer,Gate


async def failed_job(factory,call):
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),writer=Writer())
    await service.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob))
        job.status='failed';job.attempt_count=3;job.fail_reason='write_unavailable'
        job.extraction_snapshot={'version':1,'phase':'ready','items':[], 'dropped':0}
        await db.commit()
        return job.id


@pytest.mark.asyncio
async def test_retry_atomically_audits_and_retains_snapshot(memory_env):
    from backend.services.realtime_voice_job_service import retry_memory_job
    factory,call=memory_env;job_id=await failed_job(factory,call)
    admin=SimpleNamespace(id=1,username='tech',role='tech_ops')
    async with factory() as db:
        result=await retry_memory_job(db,job_id=job_id,admin=admin)
        assert result==dict(job_id=job_id,job_type='memory',status='pending',attempt_count=3)
    async with factory() as db:
        job=await db.get(VoiceMemoryJob,job_id)
        assert job.status=='pending' and job.extraction_snapshot['phase']=='ready'
        logs=(await db.scalars(select(AdminOperationLog).where(AdminOperationLog.module=='voice_job'))).all()
        assert len(logs)==1 and logs[0].action=='retry'
        assert 'extraction_snapshot' not in logs[0].after_value


@pytest.mark.asyncio
async def test_retry_audit_failure_rolls_back(memory_env,monkeypatch):
    import backend.services.realtime_voice_job_service as jobs
    factory,call=memory_env;job_id=await failed_job(factory,call)
    async def fail(*args,**kwargs): raise RuntimeError('audit unavailable')
    monkeypatch.setattr(jobs,'log_operation',fail)
    async with factory() as db:
        with pytest.raises(RuntimeError):
            await jobs.retry_memory_job(db,job_id=job_id,admin=SimpleNamespace(id=1,username='root',role='super_admin'))
    async with factory() as db:
        assert (await db.get(VoiceMemoryJob,job_id)).status=='failed'


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['fence','expired','no_snapshot','cancelled','success','processing'])
async def test_retry_rejects_unavailable_sources_and_terminal_states(memory_env,change):
    from backend.services.realtime_voice_job_service import retry_memory_job
    from backend.services.realtime_voice_config_service import VoiceConfigError
    factory,call=memory_env;job_id=await failed_job(factory,call)
    async with factory() as db:
        job=await db.get(VoiceMemoryJob,job_id)
        row=await db.scalar(select(VoiceCall))
        if change=='fence': row.deletion_fence_at=datetime.utcnow()
        elif change=='expired': row.transcript_expires_at=datetime.utcnow()-timedelta(seconds=1)
        elif change=='no_snapshot': job.extraction_snapshot=None
        else: job.status=change
        await db.commit()
    async with factory() as db:
        with pytest.raises(VoiceConfigError):
            await retry_memory_job(db,job_id=job_id,admin=SimpleNamespace(id=1,username='root',role='super_admin'))


@pytest.mark.asyncio
@pytest.mark.parametrize('role',['super_admin','tech_ops','ops_admin','ai_trainer','observer'])
async def test_http_retry_five_roles_and_no_body_disclosure(memory_env,role):
    from fastapi import FastAPI
    from httpx import AsyncClient,ASGITransport
    from backend.routers.admin.voice_ops import router
    from backend.database import get_db
    from backend.utils.admin_auth import get_current_admin
    factory,call=memory_env;job_id=await failed_job(factory,call)
    app=FastAPI();app.include_router(router,prefix='/api/admin/voice')
    app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(id=1,username=role,role=role)
    async def database():
        async with factory() as db: yield db
    app.dependency_overrides[get_db]=database
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post(f'/api/admin/voice/jobs/{job_id}/retry')
        allowed=role in {'super_admin','tech_ops'}
        assert response.status_code==(200 if allowed else 403)
        assert 'extraction_snapshot' not in response.text
        if allowed:
            assert response.headers['cache-control']=='no-store'
            again=await client.post(f'/api/admin/voice/jobs/{job_id}/retry')
            assert again.status_code==409
    async with factory() as db:
        logs=(await db.scalars(select(AdminOperationLog).where(AdminOperationLog.module=='voice_job'))).all()
        assert len(logs)==(1 if allowed else 0)


@pytest.mark.asyncio
async def test_old_call_retry_does_not_overwrite_newer_call(memory_env):
    import json
    from tests.test_realtime_voice_step009_ops import add_call,StateCache
    from backend.services.realtime_voice_job_service import retry_memory_job
    factory,old_call=memory_env;job_id=await failed_job(factory,old_call)
    item=dict(memory_type='user',stable_key='旅行-计划-目的地',content='原计划去日本')
    async with factory() as db:
        (await db.get(VoiceMemoryJob,job_id)).extraction_snapshot=dict(version=1,phase='ready',items=[item],dropped=0)
        await db.commit()
    new_call=await add_call(factory,'connected',StateCache())
    async with factory() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==new_call))
        row.config_snapshot={'resolved_script':{'memory':{'max_items_per_turn':5}}}
        await db.commit()
    writer=Writer()
    async def model(prompt): return json.dumps({'memory_items':[{**item,'content':'已改去法国'}]},ensure_ascii=False)
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=writer)
    await service.enqueue(call_id=new_call,turn_id=await add_turn(factory,new_call))
    assert await service.process_next(call_id=new_call)=='success'
    async with factory() as db:
        await retry_memory_job(db,job_id=job_id,admin=SimpleNamespace(id=1,username='root',role='super_admin'))
    assert await service.process_next(call_id=old_call)=='skipped'
    assert list(writer.docs.values())==['已改去法国']
