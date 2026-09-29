"""Actual MySQL cyclic replay of historical unique jobs and business ledger days."""
import os
from datetime import datetime
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step035_scheduler import test_late_job_and_ledger_change_recomputed_without_duplicate_rows as check_late
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL opt-in')


@pytest.mark.asyncio
async def test_mysql_scheduled_recomputation(runtime):
    factory,call_id,_=runtime
    async with factory() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call_id))
        row.created_at=datetime(2026,9,17);row.status='ended'
        await db.commit()
    await check_late(factory)
