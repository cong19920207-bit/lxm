"""Replay expiry and concurrent replay refresh against isolated MySQL."""
import asyncio
import os
from datetime import timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.models.realtime_voice import VoiceCallCreateIdempotency
from backend.services.realtime_voice_retention_service import VoiceRetentionService
from tests.test_realtime_voice_step033_runtime import containers,runtime,card_env
from tests.test_realtime_voice_step034_replay_retention import (
    replay_env,test_replay_expiry_exact_ids_and_call_metadata_survive,
    test_replay_delete_failure_rolls_back_then_same_batch_retries,
)

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


@pytest.mark.asyncio
async def test_replay_refreshed_after_candidate_snapshot_is_preserved(replay_env,monkeypatch):
    factory,_,now,ids=replay_env
    original=AsyncSession.scalars;waiting=asyncio.Event()
    async def scalars(db,statement,*args,**kwargs):
        if getattr(statement,'column_descriptions',[]) and statement.column_descriptions[0].get('entity') is User:
            waiting.set()
        return await original(db,statement,*args,**kwargs)
    task=None
    async with factory() as writer:
        await writer.scalar(select(User.id).where(User.id==1).with_for_update())
        monkeypatch.setattr(AsyncSession,'scalars',scalars)
        task=asyncio.create_task(VoiceRetentionService(session_factory=factory).purge_replays(now=now,limit=1))
        try:
            await asyncio.wait_for(waiting.wait(),5)
            row=await writer.get(VoiceCallCreateIdempotency,ids[0])
            row.replay_expires_at=now+timedelta(hours=24)
            await writer.commit()
            result=await asyncio.wait_for(task,5)
            assert result['candidate_ids']==ids[:1] and result['deleted_ids']==[]
        finally:
            if task and not task.done():task.cancel()
            if task:await asyncio.gather(task,return_exceptions=True)
    async with factory() as db:
        row=await db.get(VoiceCallCreateIdempotency,ids[0])
        assert row.replay_expires_at==now+timedelta(hours=24)
