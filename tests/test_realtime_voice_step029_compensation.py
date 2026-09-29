import json
from datetime import datetime
import pytest
import pytest_asyncio
from sqlalchemy import select
from backend.database import Base
from backend.models.realtime_voice import VoiceCall,VoiceMemoryJob,VoicePostprocessJob
from backend.models.admin_operation_log import AdminOperationLog
from backend.services.realtime_voice_memory_service import VoiceMemoryService
from tests.test_realtime_voice_step028_jobs import storage,memory_env,add_turn,Writer,Gate


@pytest_asyncio.fixture
async def compensation_env(memory_env):
    factory,call=memory_env
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=[VoicePostprocessJob.__table__,AdminOperationLog.__table__])
    try:
        yield factory,call
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=[VoicePostprocessJob.__table__])


@pytest.mark.asyncio
async def test_scheduler_discovers_ended_missing_jobs_with_atomic_audit(compensation_env):
    factory,call=compensation_env
    first=await add_turn(factory,call,1);second=await add_turn(factory,call,2)
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),writer=Writer())
    await service.enqueue(call_id=call,turn_id=first)
    assert await service.poll_compensation()==[]
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.status='ended';row.ended_at=datetime.utcnow()
        await db.commit()
    result=await service.poll_compensation()
    assert result[0]['created']==[(second,'voice_memory_v1')]
    assert await service.poll_compensation()==[]
    async with factory() as db:
        job=await db.scalar(select(VoicePostprocessJob))
        assert job.job_type=='memory_compensation' and job.status=='success'
        logs=(await db.scalars(select(AdminOperationLog).where(AdminOperationLog.action=='compensate'))).all()
        assert len(logs)==1
        snapshot=json.loads(logs[0].after_value)
        assert snapshot['created']==[[second,'voice_memory_v1']]
        assert snapshot['job_keys']==[[first,'voice_memory_v1'],[second,'voice_memory_v1']]
        assert '日本' not in logs[0].after_value


@pytest.mark.asyncio
async def test_compensation_audit_failure_rolls_back_missing_job(compensation_env,monkeypatch):
    import backend.utils.admin_auth as audit
    factory,call=compensation_env
    await add_turn(factory,call)
    async with factory() as db:
        row=await db.scalar(select(VoiceCall));row.status='ended';row.ended_at=datetime.utcnow()
        await db.commit()
    async def fail(*args,**kwargs): raise RuntimeError('audit unavailable')
    monkeypatch.setattr(audit,'log_operation',fail)
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),writer=Writer())
    with pytest.raises(RuntimeError): await service.poll_compensation()
    async with factory() as db:
        assert (await db.scalars(select(VoiceMemoryJob))).all()==[]
        assert (await db.scalars(select(VoicePostprocessJob))).all()==[]


@pytest.mark.asyncio
async def test_registered_memory_wrapper_runs_compensation(monkeypatch):
    from backend.tasks.scheduler import _run_voice_memory
    import backend.services.realtime_voice_memory_service as memory
    actions=[]
    class Service:
        async def poll(self): actions.append('consume')
        async def poll_compensation(self): actions.append('compensate')
    async def build(): return Service()
    monkeypatch.setattr(memory,'build_voice_memory_service',build)
    await _run_voice_memory()
    assert actions==['consume','compensate']
