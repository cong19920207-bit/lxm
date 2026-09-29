"""Real isolated MySQL administrative and compensation transactions."""
import asyncio
import os
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from backend.models.admin_operation_log import AdminOperationLog
from backend.services.realtime_voice_job_service import retry_memory_job
from backend.services.realtime_voice_config_service import VoiceConfigError
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step028_runtime import memory_env
from tests.test_realtime_voice_step029_compensation import (
    compensation_env,test_scheduler_discovers_ended_missing_jobs_with_atomic_audit,
    test_compensation_audit_failure_rolls_back_missing_job,
)
from tests.test_realtime_voice_step029_admin import (
    failed_job,test_retry_atomically_audits_and_retains_snapshot,
    test_retry_audit_failure_rolls_back,test_retry_rejects_unavailable_sources_and_terminal_states,
    test_http_retry_five_roles_and_no_body_disclosure,
    test_old_call_retry_does_not_overwrite_newer_call,
)
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M5_RUNTIME')!='1',reason='isolated MySQL/Redis opt-in')


@pytest.mark.asyncio
async def test_duplicate_manual_retry_has_one_audit_and_enqueue(memory_env):
    factory,call=memory_env;job_id=await failed_job(factory,call)
    async def request():
        async with factory() as db:
            try:
                await retry_memory_job(db,job_id=job_id,admin=SimpleNamespace(id=1,username='root',role='super_admin'))
                return 'queued'
            except VoiceConfigError:
                return 'rejected'
    results=await asyncio.gather(*(request() for _ in range(8)))
    assert results.count('queued')==1
    async with factory() as db:
        logs=(await db.scalars(select(AdminOperationLog).where(AdminOperationLog.module=='voice_job'))).all()
        assert len(logs)==1


@pytest.mark.asyncio
async def test_doc_guard_is_cross_connection_nonblocking_and_released(memory_env):
    from backend.services.realtime_voice_memory_service import memory_doc_session,VoiceMemoryService
    from backend.models.realtime_voice import VoiceMemoryJob
    from backend.utils.character_knowledge_validate import build_doc_id
    from tests.test_realtime_voice_step028_jobs import add_turn,Gate,Writer
    from datetime import datetime,timedelta
    factory,call=memory_env
    writer=Writer()
    async def model(prompt):
        return '{"memory_items":[{"memory_type":"user","stable_key":"旅行-计划-日本","content":"下月去日本"}]}'
    service=VoiceMemoryService(session_factory=factory,gate=Gate(),model=model,writer=writer)
    await service.enqueue(call_id=call,turn_id=await add_turn(factory,call))
    doc=build_doc_id('user','旅行-计划-日本',1)
    async with memory_doc_session(factory,doc):
        assert await asyncio.wait_for(service.process_next(call_id=call),2)=='failed'
        assert writer.calls==[]
    async with factory() as db:
        job=await db.scalar(select(VoiceMemoryJob))
        job.next_retry_at=datetime.utcnow()-timedelta(seconds=1)
        await db.commit()
    assert await service.poll()==['success']
    assert len(writer.calls)==1
    # Reusing the pool must not inherit any named lock from the previous write.
    async with memory_doc_session(factory,doc):
        pass
