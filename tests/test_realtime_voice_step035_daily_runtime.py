"""Business-day SQL projection on actual isolated MySQL."""
import os
from datetime import datetime
import pytest
from sqlalchemy import select
from backend.models.realtime_voice import VoiceCall
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step035_daily import test_shanghai_boundary_unique_tasks_and_cross_day_ledger as check_day
pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated MySQL opt-in')


@pytest.mark.asyncio
async def test_mysql_business_day_cohort_and_ledger(runtime):
    factory,call,_=runtime
    async with factory() as db:
        row=await db.scalar(select(VoiceCall).where(VoiceCall.call_id==call))
        row.created_at=datetime(2000,1,1)
        await db.commit()
    await check_day(factory)
