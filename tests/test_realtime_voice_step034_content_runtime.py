"""Actual MySQL content cleanup and Redis failure recovery; no business data."""
import os
import asyncio
from datetime import datetime,timedelta
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall,VoiceCallTurn,VoiceMemoryJob
from backend.services.realtime_voice_retention_service import VoiceRetentionService
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step034_content_retention import (
    seed,test_content_expiry_exact_object_projection_and_independent_summary,
    test_retention_types_do_not_shorten_other_lifecycles,
)

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


@pytest.mark.asyncio
async def test_content_cache_failure_rolls_back_then_clears_real_cache(card_env,runtime):
    factory,call_id=card_env;_,_,cache=runtime;now=datetime(2026,9,14,4)
    turn_id,_,_,_=await seed(factory,call_id,now,now)
    key=f'voice:session_context:{call_id}'
    await cache.set(key,'private-context')
    class FailedCache:
        async def delete(self,key):raise ConnectionError('controlled unavailable cache')
    with pytest.raises(ConnectionError):
        await VoiceRetentionService(session_factory=factory,cache=FailedCache()).purge_contents(now=now)
    async with factory() as db:
        turn=await db.get(VoiceCallTurn,turn_id)
        assert turn.user_text_final=='下月去日本' and turn.effective_text_cleared_at is None
    assert await cache.get(key)=='private-context'
    result=await VoiceRetentionService(session_factory=factory,cache=cache).purge_contents(now=now)
    assert result['reports'][0]['cache_keys']==[key]
    assert await cache.get(key) is None
    async with factory() as db:
        turn=await db.get(VoiceCallTurn,turn_id)
        assert turn.user_text_final is None and turn.effective_text_cleared_at==now


@pytest.mark.asyncio
async def test_unexpired_live_call_does_not_wait_on_vector_writer_lock(card_env,runtime):
    factory,call_id=card_env;_,_,cache=runtime;now=datetime(2026,9,14,4)
    _,_,jobs,_=await seed(factory,call_id,now,now+timedelta(days=1))
    async with factory() as db:
        call=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id));call.status='connected'
        job=await db.get(VoiceMemoryJob,jobs[0]);job.status='processing';await db.commit()
    async with factory() as writer:
        await writer.scalar(select(VoiceMemoryJob.id).where(VoiceMemoryJob.id==jobs[0]).with_for_update())
        result=await asyncio.wait_for(VoiceRetentionService(session_factory=factory,cache=cache)
            .purge_contents(now=now),1)
        assert all(not report['changed'] for report in result['reports'])
