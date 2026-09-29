"""STEP-032 admission against owned disposable MySQL/Redis infrastructure."""
import asyncio
import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select,func

from backend.database import Base
from backend.models.realtime_voice import VoiceCall,VoiceFollowupJob,VoicePostprocessJob
from backend.models.relationship import Relationship
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step032_followup import (
    test_missed_transition_stages_exact_message_without_summary,
    test_missed_frozen_window_and_same_call_idempotency,
    test_non_missed_never_gets_deterministic_explanation,
    test_missed_finalizer_and_first_user_default_stage,
    test_missed_failure_rolls_back_terminal_card_and_job,
)

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


@pytest_asyncio.fixture
async def card_env(runtime):
    factory,call_id,_=runtime
    tables=[m.__table__ for m in (Relationship,VoiceFollowupJob,VoicePostprocessJob)]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=tables)
    try:yield factory,call_id
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=tables)


@pytest.mark.asyncio
async def test_concurrent_missed_transition_is_one_card_one_job(card_env):
    from backend.services.realtime_voice_state_service import transition_call
    factory,call_id=card_env
    async with factory() as db:
        call=await db.scalar(select(VoiceCall));call.status='deciding';call.connected_at=None
        await db.commit()
    async def finish():
        async with factory() as db:
            return await transition_call(db,call_id=call_id,expected=('deciding',),target='missed',now=datetime.now(timezone.utc))
    assert sorted(await asyncio.gather(finish(),finish()))==[False,True]
    async with factory() as db:
        call=await db.scalar(select(VoiceCall))
        assert call.status=='missed' and call.sort_seq==1
        assert await db.scalar(select(func.count()).select_from(VoiceFollowupJob))==1
